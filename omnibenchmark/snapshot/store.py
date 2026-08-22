"""Snapshot descriptors, the local registry, and the commit protocol.

See docs/design/012-incremental-snapshots.md §3.3/§3.4. Phase 1 ships only the
directory-backed store: on a cluster the shared filesystem *is* the remote, so
this is the whole SLURM story. The S3 store arrives with the tar archives.

Readiness (§3.3.1). A snapshot is consumable only once ``snapshot.json``
exists, and that file is written **last** and atomically. Payload first,
manifest second, descriptor last — an interrupted publish therefore leaves a
directory that ``list`` and ``resolve`` simply do not see, rather than a
half-snapshot that reads as complete.

Integrity is a chain rooted in that descriptor: it carries the sha256 of
``MANIFEST``, and ``MANIFEST`` carries the size and sha256 of every file. A
consumer can therefore verify everything it received from one atomically
written record.
"""

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from omnibenchmark.snapshot.extent import Extent
from omnibenchmark.snapshot.link import place, sha256

DESCRIPTOR = "snapshot.json"
MANIFEST = "MANIFEST"
DEFAULT_REGISTRY = Path(".ob/cache")


class SnapshotIntegrityError(Exception):
    """A snapshot's payload does not match what its descriptor promises."""


@dataclass(frozen=True)
class Snapshot:
    benchmark_id: str
    version: str
    extent: Extent
    label_stage: Optional[str] = None
    ob_version: Optional[str] = None
    n_files: int = 0
    manifest_sha256: Optional[str] = None
    # Recorded for the compatibility gate (§3.2/§3.8); absent on snapshots
    # published before the gate existed, which then skip those checks.
    prefix_hash: Optional[str] = None
    host: Optional[dict] = None

    @property
    def id(self) -> str:
        return f"{self.benchmark_id}/{self.version}/{self.extent.key()}"

    def to_dict(self) -> dict:
        return {
            "benchmark_id": self.benchmark_id,
            "version": self.version,
            "extent": self.extent.to_dict(),
            "label_stage": self.label_stage,
            "ob_version": self.ob_version,
            "n_files": self.n_files,
            "manifest_sha256": self.manifest_sha256,
            "prefix_hash": self.prefix_hash,
            "host": self.host,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Snapshot":
        return cls(
            benchmark_id=d["benchmark_id"],
            version=d["version"],
            extent=Extent.from_dict(d["extent"]),
            label_stage=d.get("label_stage"),
            ob_version=d.get("ob_version"),
            n_files=d.get("n_files", 0),
            manifest_sha256=d.get("manifest_sha256"),
            prefix_hash=d.get("prefix_hash"),
            host=d.get("host"),
        )


def _write_manifest(dest: Path, digests: Dict[str, str], links: List[str]) -> str:
    """Write the per-file record and return its own sha256."""
    lines = [
        f"f\t{rel}\t{(dest / rel).stat().st_size}\t{digest}"
        for rel, digest in sorted(digests.items())
    ]
    lines += [f"l\t{rel}\t{os.readlink(dest / rel)}" for rel in sorted(links)]
    path = dest / MANIFEST
    path.write_text("\n".join(lines) + "\n")
    return sha256(path)


def read_manifest(snap_dir: Path) -> Tuple[Dict[str, Tuple[int, str]], List[str]]:
    """Parse MANIFEST into ``({path: (size, sha256)}, [symlink paths])``."""
    files: Dict[str, Tuple[int, str]] = {}
    links: List[str] = []
    for line in (snap_dir / MANIFEST).read_text().splitlines():
        if not line:
            continue
        kind, rest = line.split("\t", 1)
        if kind == "f":
            rel, size, digest = rest.rsplit("\t", 2)
            files[rel] = (int(size), digest)
        else:
            links.append(rest.split("\t", 1)[0])
    return files, links


def verify(snap_dir: Path, deep: bool = True) -> None:
    """Check a snapshot against its own descriptor.

    Shallow (``deep=False``) checks presence and size, which is what catches a
    truncated or missing payload and costs only a stat per file. Deep re-reads
    every byte. Raises :class:`SnapshotIntegrityError` on the first mismatch.
    """
    snap = LocalSnapshotStore.load(snap_dir)
    if snap.manifest_sha256 and sha256(snap_dir / MANIFEST) != snap.manifest_sha256:
        raise SnapshotIntegrityError(
            f"{snap_dir}: MANIFEST does not match the descriptor"
        )

    files, links = read_manifest(snap_dir)
    for rel, (size, digest) in files.items():
        path = snap_dir / rel
        if not path.is_file():
            raise SnapshotIntegrityError(f"{snap_dir}: missing {rel}")
        if path.stat().st_size != size:
            raise SnapshotIntegrityError(
                f"{snap_dir}: {rel} is {path.stat().st_size} bytes, expected {size}"
            )
        if deep and sha256(path) != digest:
            raise SnapshotIntegrityError(f"{snap_dir}: {rel} failed checksum")
    for rel in links:
        if not (snap_dir / rel).is_symlink():
            raise SnapshotIntegrityError(f"{snap_dir}: missing symlink {rel}")


def materialize(snap_dir: Path, out_dir: Path, deep: bool = False) -> List[str]:
    """Hardlink a snapshot's payload into *out_dir*.

    Verified before anything is linked, so a bad snapshot never half-populates a
    working directory. The default check is size-and-presence: materialising
    reads no bytes, so a full digest pass would be the most expensive step of an
    otherwise instant operation. Use ``deep=True`` (``--verify``) to pay for it.
    """
    verify(snap_dir, deep=deep)
    files, links = read_manifest(snap_dir)
    place(snap_dir, out_dir, sorted(files), sorted(links))
    return sorted(files) + sorted(links)


class LocalSnapshotStore:
    """A directory of snapshots, laid out as ``<benchmark>/<version>/<key>/``."""

    def __init__(self, root: Path = DEFAULT_REGISTRY):
        self.root = Path(root)

    def path(self, snap: Snapshot) -> Path:
        return self.root / snap.benchmark_id / snap.version / snap.extent.key()

    def push(
        self,
        snap: Snapshot,
        out_dir: Path,
        files: List[str],
        links: List[str],
        force: bool = False,
    ) -> Path:
        dest = self.path(snap)
        if (dest / DESCRIPTOR).is_file() and not force:
            raise FileExistsError(
                f"{snap.id} already published at {dest}. Use --force to replace it."
            )
        dest.mkdir(parents=True, exist_ok=True)
        # A previous descriptor is removed first: while the payload is being
        # rewritten the snapshot must not read as consumable.
        (dest / DESCRIPTOR).unlink(missing_ok=True)

        # Copy rather than link: hardlinking would share the read-only mode with
        # the working tree and freeze it as a side effect of publishing.
        digests = place(out_dir, dest, files, links, copy=True, protect=True)
        manifest_sha = _write_manifest(dest, digests, links)

        complete = replace(snap, manifest_sha256=manifest_sha)
        tmp = dest / (DESCRIPTOR + ".tmp")
        tmp.write_text(json.dumps(complete.to_dict(), indent=2) + "\n")
        os.replace(tmp, dest / DESCRIPTOR)  # atomic: the commit point
        return dest

    def list(self, benchmark_id: Optional[str] = None) -> List[Snapshot]:
        pattern = f"{benchmark_id or '*'}/*/*/{DESCRIPTOR}"
        return [
            Snapshot.from_dict(json.loads(p.read_text()))
            for p in sorted(self.root.glob(pattern))
        ]

    def resolve(self, ref: str) -> Path:
        """Locate a snapshot by directory path or by id."""
        for candidate in (Path(ref), self.root / ref):
            if (candidate / DESCRIPTOR).is_file():
                return candidate
        raise FileNotFoundError(
            f"no consumable snapshot at {ref!r} (looked in {Path(ref)} and "
            f"{self.root / ref}). An interrupted publish leaves no descriptor."
        )

    @staticmethod
    def load(path: Path) -> Snapshot:
        return Snapshot.from_dict(json.loads((path / DESCRIPTOR).read_text()))
