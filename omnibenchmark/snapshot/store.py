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

from omnibenchmark.snapshot.extent import Extent, lineage
from omnibenchmark.snapshot.link import included, link_chain, place, select, sha256

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
    # "published" — committed into a registry, digests recorded, immutable.
    # "local"     — derived from a working output tree: no digests, and nothing
    #               stops it changing under us. Reusable, but not reproducible:
    #               it cannot be re-fetched and a pointer to it can dangle.
    source: str = "published"
    path: Optional[str] = None

    @property
    def id(self) -> str:
        stem = f"{self.benchmark_id}/{self.version}/{self.extent.key()}"
        return stem if self.source == "published" else f"local:{stem}"

    @property
    def reproducible(self) -> bool:
        """Whether this can be fetched again and checked against what it was."""
        return self.source == "published"

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
            "source": self.source,
            "path": self.path,
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
            source=d.get("source", "published"),
            path=d.get("path"),
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


def read_manifest(snap_dir: Path) -> Tuple[Dict[str, Tuple[int, str]], Dict[str, str]]:
    """Parse MANIFEST into ``({path: (size, sha256)}, {symlink path: target})``."""
    files: Dict[str, Tuple[int, str]] = {}
    links: Dict[str, str] = {}
    for line in (snap_dir / MANIFEST).read_text().splitlines():
        if not line:
            continue
        kind, rest = line.split("\t", 1)
        if kind == "f":
            rel, size, digest = rest.rsplit("\t", 2)
            files[rel] = (int(size), digest)
        else:
            rel, target = rest.split("\t", 1)
            links[rel] = target
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


def materialize(
    snap_dir: Path,
    out_dir: Path,
    want: Optional[Extent] = None,
    deep: bool = False,
) -> List[str]:
    """Hardlink a snapshot's payload into *out_dir*.

    *want* narrows what is taken. A snapshot that covers three stages and four
    datasets can seed a run that only wants the first two stages of one dataset;
    the caller has already checked ``snapshot.extent.covers(want)``, and this
    filters the payload to it. Without *want* the whole snapshot is taken.

    Verified before anything is linked, so a bad snapshot never half-populates a
    working directory. The default check is size-and-presence: materialising
    reads no bytes, so a full digest pass would be the most expensive step of an
    otherwise instant operation. Use ``deep=True`` (``--verify``) to pay for it.
    """
    verify(snap_dir, deep=deep)
    snap = LocalSnapshotStore.load(snap_dir)
    files, links = read_manifest(snap_dir)
    if want is not None:
        files = {
            rel: meta
            for rel, meta in files.items()
            if included(lineage(rel), want, snap.label_stage)
        }
        links = {
            rel: target
            for rel, target in links.items()
            if included(link_chain(rel, target), want, snap.label_stage)
        }
    place(snap_dir, out_dir, sorted(files), sorted(links))
    return sorted(files) + sorted(links)


def materialize_tree(
    base_dir: Path, out_dir: Path, snap: "Snapshot", want: Extent
) -> List[str]:
    """Hardlink part of a plain output tree into *out_dir*.

    The unpublished counterpart of :func:`materialize`: an output directory is
    already laid out like a snapshot's payload, so the extent is read straight
    off the paths. No digests exist, and none are needed — a live directory has
    no wire in flight to corrupt it — but nothing here can detect the base
    changing underneath, which is what ``source="local"`` records.
    """
    files, links = select(base_dir, want, snap.label_stage)
    place(base_dir, out_dir, files, links)
    return files + links


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


def snapshot_of_tree(
    base_dir: Path, extent: Extent, label_stage: Optional[str]
) -> Snapshot:
    """Describe a plain output tree as a snapshot, without publishing it.

    An output directory already carries everything the gate needs: the plan it
    was produced under (`.metadata/benchmark.yaml`) and the machine that
    produced it (`.metadata/manifest.json`). So reusing a colleague's `out/`
    needs no new concepts — only a descriptor built in memory instead of read
    from disk, marked ``source="local"`` because it has no digests and may
    change under us.
    """
    import json as _json

    from omnibenchmark.backend._runlog import host_record

    metadata = Path(base_dir) / ".metadata"
    plan = metadata / "benchmark.yaml"
    if not plan.is_file():
        raise FileNotFoundError(
            f"{base_dir} is neither a published snapshot nor an output directory "
            f"(no {plan}). Only trees produced by `ob run` can be reused directly."
        )

    from omnibenchmark.model import Benchmark as BenchmarkModel

    model = BenchmarkModel.from_yaml(plan)
    host = None
    manifest = metadata / "manifest.json"
    if manifest.is_file():
        try:
            host = host_record(_json.loads(manifest.read_text()))
        except (OSError, _json.JSONDecodeError):
            host = None

    from omnibenchmark.snapshot.compat import prefix_hash

    return Snapshot(
        benchmark_id=model.get_name(),
        version=model.get_version(),
        extent=extent,
        label_stage=label_stage,
        prefix_hash=prefix_hash(model, extent.stages),
        host=host,
        source="local",
        path=str(Path(base_dir).resolve()),
    )


def imported_paths(out_dir: Path, registry: Optional[Path] = None) -> set:
    """Relative paths in *out_dir* that came from a published snapshot.

    Read from the run log's ``starts_from`` and the named snapshots' own
    MANIFESTs — a lookup, never an inode heuristic (§3.6).

    Only *published* sources count. A local base cannot be pointed at, so
    anything taken from one has to travel with the archive rather than be
    subtracted from it (§3.3.2). A source that cannot be resolved is skipped for
    the same reason: if we cannot say what it holds, we must not drop files on
    the assumption it holds them.
    """
    from omnibenchmark.backend._runlog import read_runs

    store = LocalSnapshotStore(registry or DEFAULT_REGISTRY)
    paths: set = set()
    for run in read_runs(out_dir):
        for ref in run.get("starts_from") or ():
            if not ref or str(ref).startswith("local:"):
                continue
            try:
                files, links = read_manifest(store.resolve(str(ref)))
            except (FileNotFoundError, OSError, ValueError):
                continue
            paths.update(files)
            paths.update(links)
    return paths
