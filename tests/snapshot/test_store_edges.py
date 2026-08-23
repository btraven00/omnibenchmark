"""Edges of the store and materialiser: manifests, EXDEV, subtraction."""

import errno
import json
import os

import pytest

from omnibenchmark.snapshot import (
    Extent,
    LocalSnapshotStore,
    Snapshot,
    SnapshotIntegrityError,
    place,
    select,
    verify,
)
from omnibenchmark.snapshot.extent import lineage, slice_value
from omnibenchmark.snapshot.link import included, link_chain
from omnibenchmark.snapshot.store import (
    MANIFEST,
    imported_paths,
    read_manifest,
    snapshot_of_tree,
)

PLAN = """
id: bench
version: "1.0.0"
benchmarker: tester
api_version: "0.3.0"
software_backend: host
software_environments:
  py: {description: python, conda: envs/py.yaml}
stages:
  - id: data
    modules:
      - id: D1
        software_environment: py
        repository: {url: https://example.org/d.git, commit: aaaaaaa}
    outputs:
      - {id: data.matrix, path: "matrix.csv"}
"""


@pytest.fixture
def tree(tmp_path):
    out = tmp_path / "out"
    for rel in [
        "data/D1/.default/f.txt",
        "data/D1/.default/process/P1/.abc/g.txt",
    ]:
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(rel)
    os.symlink(".abc", out / "data/D1/.default/process/P1/alias")
    (out / ".metadata").mkdir()
    (out / ".metadata" / "benchmark.yaml").write_text(PLAN)
    return out


def publish(tree, tmp_path, stages=("data", "process")):
    extent = Extent(frozenset(stages), "dataset", frozenset())
    files, links = select(tree, extent, "data")
    snap = Snapshot("bench", "1.0.0", extent, label_stage="data", n_files=len(files))
    store = LocalSnapshotStore(tmp_path / "reg")
    return store, store.push(snap, tree, files, links)


# ------------------------------------------------------------------ MANIFEST


def test_manifest_round_trips_files_and_link_targets(tree, tmp_path):
    _, snap_dir = publish(tree, tmp_path)
    files, links = read_manifest(snap_dir)
    assert set(files) == {
        "data/D1/.default/f.txt",
        "data/D1/.default/process/P1/.abc/g.txt",
    }
    assert links == {"data/D1/.default/process/P1/alias": ".abc"}
    size, digest = files["data/D1/.default/f.txt"]
    assert size > 0 and len(digest) == 64


def test_blank_manifest_lines_are_ignored(tree, tmp_path):
    _, snap_dir = publish(tree, tmp_path)
    body = (snap_dir / MANIFEST).read_text()
    (snap_dir / MANIFEST).write_text("\n\n" + body + "\n\n")
    files, links = read_manifest(snap_dir)
    assert len(files) == 2 and len(links) == 1


def test_a_missing_symlink_fails_verification(tree, tmp_path):
    _, snap_dir = publish(tree, tmp_path)
    (snap_dir / "data/D1/.default/process/P1/alias").unlink()
    with pytest.raises(SnapshotIntegrityError, match="missing symlink"):
        verify(snap_dir, deep=False)


# -------------------------------------------------------------------- resolve


def test_a_snapshot_resolves_by_id_as_well_as_by_path(tree, tmp_path):
    store, snap_dir = publish(tree, tmp_path)
    snap = LocalSnapshotStore.load(snap_dir)
    assert store.resolve(snap.id) == snap_dir
    assert store.resolve(str(snap_dir)) == snap_dir


def test_an_unknown_reference_names_both_places_it_looked(tmp_path):
    store = LocalSnapshotStore(tmp_path / "reg")
    with pytest.raises(FileNotFoundError, match="looked in"):
        store.resolve("bench/1.0.0/deadbeef")


# ----------------------------------------------------------------- hardlinks


def test_a_cross_device_link_is_an_error_naming_the_fix(tree, tmp_path, monkeypatch):
    def cross_device(src, dst):
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(os, "link", cross_device)
    with pytest.raises(RuntimeError, match="same volume|one\n?\\s*volume"):
        place(tree, tmp_path / "w", ["data/D1/.default/f.txt"], [])


def test_other_link_errors_are_not_disguised(tree, tmp_path, monkeypatch):
    def denied(src, dst):
        raise OSError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(os, "link", denied)
    with pytest.raises(OSError) as excinfo:
        place(tree, tmp_path / "w", ["data/D1/.default/f.txt"], [])
    assert excinfo.value.errno == errno.EACCES


def test_placing_twice_is_idempotent(tree, tmp_path):
    files, links = select(tree, Extent(frozenset({"data", "process"})), "data")
    place(tree, tmp_path / "w", files, links)
    place(tree, tmp_path / "w", files, links)  # must not raise on existing paths
    assert (tmp_path / "w/data/D1/.default/f.txt").stat().st_nlink == 2
    assert (tmp_path / "w/data/D1/.default/process/P1/alias").is_symlink()


# ------------------------------------------------------- predicates in detail


def test_a_path_outside_the_layout_belongs_to_no_slice():
    assert included(lineage("stray.txt"), Extent(frozenset({"data"})), "data") is False


def test_no_label_stage_means_every_node_is_trunk():
    assert slice_value([("data", "D1")], None) is None


def test_a_link_is_judged_by_its_target_not_its_own_name():
    assert link_chain("data/D1/.default/process/P1/alias", ".abc") == [
        ("data", "D1"),
        ("process", "P1"),
    ]


# ------------------------------------------------------- derived descriptors


def test_a_damaged_manifest_leaves_the_host_unknown_not_the_tree_unusable(tree):
    (tree / ".metadata" / "manifest.json").write_text("{not json")
    snap = snapshot_of_tree(tree, Extent(frozenset({"data"}), "dataset"), "data")
    assert snap.host is None and snap.source == "local"


# ------------------------------------------------------------- subtraction


def _log(out_dir, starts_from):
    meta = out_dir / ".metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "runs.jsonl").write_text(
        json.dumps({"run_id": "r", "starts_from": starts_from, "imported": 0}) + "\n"
    )


def test_nothing_is_subtracted_without_a_run_log(tmp_path):
    assert imported_paths(tmp_path, tmp_path / "reg") == set()


def test_files_from_a_published_source_are_subtracted(tree, tmp_path):
    store, snap_dir = publish(tree, tmp_path)
    snap = LocalSnapshotStore.load(snap_dir)
    work = tmp_path / "work"
    _log(work, [snap.id])
    assert imported_paths(work, store.root) == {
        "data/D1/.default/f.txt",
        "data/D1/.default/process/P1/.abc/g.txt",
        "data/D1/.default/process/P1/alias",
    }


def test_a_local_base_is_never_subtracted(tree, tmp_path):
    store, _ = publish(tree, tmp_path)
    work = tmp_path / "work"
    _log(work, ["local:bench/1.0.0/deadbeef"])
    # A pointer to an unpublished tree would dangle, so its files must travel.
    assert imported_paths(work, store.root) == set()


def test_an_unresolvable_source_is_kept_rather_than_guessed(tmp_path):
    work = tmp_path / "work"
    _log(work, ["bench/9.9.9/cafebabe"])
    assert imported_paths(work, tmp_path / "reg") == set()


def test_several_sources_accumulate(tree, tmp_path):
    store, snap_dir = publish(tree, tmp_path)
    narrow = publish(tree, tmp_path, stages=("data",))[1]
    work = tmp_path / "work"
    ids = [LocalSnapshotStore.load(d).id for d in (snap_dir, narrow)]
    _log(work, ids)
    assert "data/D1/.default/f.txt" in imported_paths(work, store.root)


def test_verification_passes_over_intact_symlinks(tree, tmp_path):
    _, snap_dir = publish(tree, tmp_path)
    verify(snap_dir, deep=True)  # must not raise: links are present and correct


def test_a_tree_with_no_manifest_still_describes_itself(tree):
    # An output directory from a run that never wrote host metadata.
    assert not (tree / ".metadata" / "manifest.json").exists()
    snap = snapshot_of_tree(tree, Extent(frozenset({"data"}), "dataset"), "data")
    assert snap.host is None
    assert snap.benchmark_id == "bench" and snap.prefix_hash
