"""Selecting a slice out of an output tree, and putting it back with hardlinks.

See docs/design/012-incremental-snapshots.md §3.5. Materialising a fetched
slice is a plain walk: at the working scale (50k files) hardlinking measures
~1.2 s, so there is nothing here to batch or parallelise.
"""

import errno
import hashlib
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from omnibenchmark.snapshot.extent import Extent, lineage, slice_value

# Provenance and machinery directories, never part of a slice. `.snakemake`
# is excluded deliberately: shipping its records can only add reruns, never
# prevent one (012 §3.5).
SKIP_TOP = {".snakemake", ".logs", ".modules", ".metadata", "Snakefile"}

# Registry files are read-only so an in-place write cannot reach the shared
# cache through a hardlink. Snakemake turns this into a named
# ProtectedOutputException instead of silent corruption (012 §3.5).
REGISTRY_MODE = 0o444


def link_chain(rel: str, target: str):
    """Lineage of a symlink alias: judged by its target, never by its own path."""
    parent = os.path.dirname(rel)
    return lineage(os.path.join(parent, target) if parent else target)


def included(chain, extent: Extent, label_stage: Optional[str]) -> bool:
    if not chain:
        return False
    if not all(stage in extent.stages for stage, _ in chain):
        return False
    if extent.all_values():
        return True
    value = slice_value(chain, label_stage)
    # None means trunk — shared by every branch, so always included.
    return value is None or value in extent.slice_values


def select(
    out_dir: Path, extent: Extent, label_stage: Optional[str] = None
) -> Tuple[List[str], List[str]]:
    """Relative paths of the (files, symlinks) inside *extent*.

    Symlinks are the human-readable parameter aliases from ``core/symlinks.py``.
    They are judged by their target, not by their own path, and recreated rather
    than linked — ``os.link`` would dereference them.
    """
    files: List[str] = []
    links: List[str] = []
    for root, dirnames, filenames in os.walk(out_dir, followlinks=False):
        rel_root = Path(root).relative_to(out_dir)
        if rel_root == Path("."):
            dirnames[:] = [d for d in dirnames if d not in SKIP_TOP]
            filenames = [f for f in filenames if f not in SKIP_TOP]

        for name in list(dirnames):
            if os.path.islink(os.path.join(root, name)):
                dirnames.remove(name)
                rel = (rel_root / name).as_posix()
                target = os.readlink(os.path.join(root, name))
                if included(link_chain(rel, target), extent, label_stage):
                    links.append(rel)

        for name in filenames:
            rel = (rel_root / name).as_posix()
            if included(lineage(rel), extent, label_stage):
                files.append(rel)
    return sorted(files), sorted(links)


def _copy_and_hash(src: Path, dst: Path) -> str:
    """Copy *src* to *dst*, returning its sha256.

    Hashing rides along with the copy, so integrity costs no extra read pass.
    """
    digest = hashlib.sha256()
    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
        while chunk := fsrc.read(1 << 20):
            digest.update(chunk)
            fdst.write(chunk)
    shutil.copystat(src, dst)
    return digest.hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _place(src: Path, dst: Path, copy: bool) -> Optional[str]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        return None
    if copy:
        return _copy_and_hash(src, dst)
    try:
        os.link(src, dst)
    except OSError as e:
        if e.errno == errno.EXDEV:
            raise RuntimeError(
                f"cannot hardlink {src} -> {dst}: different filesystems. "
                "The snapshot registry and the output directory must be on one "
                "volume; move the registry (--registry) or the output directory."
            ) from e
        raise


def place(
    src_root: Path,
    dst_root: Path,
    files: List[str],
    links: List[str],
    copy: bool = False,
    protect: bool = False,
) -> Dict[str, str]:
    """Mirror *files* and *links* from one tree into another.

    copy=True duplicates bytes (used when publishing into the registry, so the
    working tree is not turned read-only as a side effect); the default
    hardlinks. protect=True marks the placed files read-only.

    Returns ``{relative path: sha256}`` for copied files — empty digests when
    hardlinking, since no bytes were read.
    """
    digests: Dict[str, str] = {}
    for rel in files:
        digest = _place(src_root / rel, dst_root / rel, copy)
        if digest:
            digests[rel] = digest
        if protect:
            os.chmod(dst_root / rel, REGISTRY_MODE)
    for rel in links:
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() and not dst.is_symlink():
            os.symlink(os.readlink(src_root / rel), dst)
    return digests
