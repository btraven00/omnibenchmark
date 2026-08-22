"""Phase 1 of design/012: extent algebra, layout decoding, materialisation."""

import os

import pytest

from omnibenchmark.snapshot import (
    Extent,
    LocalSnapshotStore,
    Snapshot,
    SnapshotIntegrityError,
    lineage,
    materialize,
    place,
    select,
    verify,
)
from omnibenchmark.snapshot.link import REGISTRY_MODE
from omnibenchmark.snapshot.store import DESCRIPTOR, MANIFEST


# --------------------------------------------------------------------------- extent


def test_covers_is_stage_containment_and_branch_containment():
    both = Extent(frozenset({"data", "process"}), "dataset", frozenset({"D1", "D2"}))
    one = Extent(frozenset({"data"}), "dataset", frozenset({"D1"}))
    assert both.covers(one)
    assert not one.covers(both)


def test_empty_slice_values_means_every_branch():
    everything = Extent(frozenset({"data"}), "dataset", frozenset())
    just_d1 = Extent(frozenset({"data"}), "dataset", frozenset({"D1"}))
    assert everything.covers(just_d1)
    # ...and a single branch does not cover "all branches".
    assert not just_d1.covers(everything)


def test_a_different_label_never_covers():
    by_dataset = Extent(frozenset({"data"}), "dataset", frozenset({"D1"}))
    by_cohort = Extent(frozenset({"data"}), "cohort", frozenset({"D1"}))
    assert not by_dataset.covers(by_cohort)


def test_union_accumulates_branches_and_rejects_mixed_labels():
    a = Extent(frozenset({"data"}), "dataset", frozenset({"D1"}))
    b = Extent(frozenset({"process"}), "dataset", frozenset({"D2"}))
    assert (a | b) == Extent(
        frozenset({"data", "process"}), "dataset", frozenset({"D1", "D2"})
    )
    with pytest.raises(ValueError):
        a | Extent(frozenset({"data"}), "cohort", frozenset({"X"}))


def test_key_is_stable_under_member_ordering():
    a = Extent(frozenset({"data", "process"}), "dataset", frozenset({"D1", "D2"}))
    b = Extent(frozenset({"process", "data"}), "dataset", frozenset({"D2", "D1"}))
    assert a.key() == b.key()
    assert a.key() != Extent(frozenset({"data"}), "dataset").key()


# --------------------------------------------------------------------------- layout


def test_lineage_reads_stage_module_triples():
    assert lineage("data/D1/.default/process/P1/.abc123/x.txt") == [
        ("data", "D1"),
        ("process", "P1"),
    ]


def test_lineage_stops_at_module_internal_subdirectories():
    # `sub/` is written by the module, not by the layout: it must not be read
    # as another stage.
    assert lineage("data/D1/.default/sub/nested.txt") == [("data", "D1")]


# --------------------------------------------------------------------------- fixture


@pytest.fixture
def out_tree(tmp_path):
    out = tmp_path / "out"
    files = [
        "data/D1/.default/f.txt",
        "data/D1/.default/sub/nested.txt",
        "data/D2/.default/f.txt",
        "data/D1/.default/process/P1/.abc123/g.txt",
        "data/D2/.default/process/P1/.abc123/g.txt",
        ".logs/run.log",
        ".snakemake/metadata/xyz",
        "Snakefile",
    ]
    for rel in files:
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"contents of {rel}\n")
    os.symlink(".abc123", out / "data/D1/.default/process/P1/alias")
    return out


# --------------------------------------------------------------------------- select


def test_select_cuts_vertically_and_skips_machinery(out_tree):
    files, links = select(out_tree, Extent(frozenset({"data"})), "data")
    assert files == [
        "data/D1/.default/f.txt",
        "data/D1/.default/sub/nested.txt",
        "data/D2/.default/f.txt",
    ]
    assert links == []


def test_select_cuts_horizontally_by_branch(out_tree):
    extent = Extent(frozenset({"data", "process"}), "dataset", frozenset({"D1"}))
    files, links = select(out_tree, extent, "data")
    assert all(rel.startswith("data/D1/") for rel in files)
    # The alias is judged by its target, which lives in an included branch.
    assert links == ["data/D1/.default/process/P1/alias"]


def test_select_keeps_the_trunk_regardless_of_branch(tmp_path):
    # Labelling stage is *not* first: `download` is above the cut and shared.
    out = tmp_path / "out"
    for rel in [
        "download/raw/.default/all.tar",
        "download/raw/.default/dataset/D1/.h/x.txt",
        "download/raw/.default/dataset/D2/.h/x.txt",
    ]:
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(rel)

    extent = Extent(frozenset({"download", "dataset"}), "dataset", frozenset({"D1"}))
    files, _ = select(out, extent, "dataset")
    assert files == [
        "download/raw/.default/all.tar",  # trunk: no branch, always included
        "download/raw/.default/dataset/D1/.h/x.txt",
    ]


# --------------------------------------------------------------------------- place


def test_place_hardlinks_and_recreates_symlinks(out_tree, tmp_path):
    dst = tmp_path / "work"
    files, links = select(
        out_tree, Extent(frozenset({"data", "process"}), None), "data"
    )
    place(out_tree, dst, files, links)

    linked = dst / "data/D1/.default/f.txt"
    assert linked.stat().st_ino == (out_tree / "data/D1/.default/f.txt").stat().st_ino
    assert linked.stat().st_nlink == 2
    alias = dst / "data/D1/.default/process/P1/alias"
    assert alias.is_symlink() and os.readlink(alias) == ".abc123"


# ------------------------------------------------------------------ commit protocol


def _publish(out_tree, registry, extent=None, **kw):
    extent = extent or Extent(frozenset({"data"}), "dataset", frozenset())
    files, links = select(out_tree, extent, "data")
    snap = Snapshot("bench", "1.0.0", extent, label_stage="data", n_files=len(files))
    store = LocalSnapshotStore(registry)
    return store, store.push(snap, out_tree, files, links, **kw)


def test_push_then_materialise_round_trip(out_tree, tmp_path):
    store, snap_dir = _publish(out_tree, tmp_path / "registry")
    fresh = tmp_path / "fresh"
    imported = materialize(snap_dir, fresh)

    assert (fresh / "data/D1/.default/f.txt").read_text().startswith("contents of")
    assert "data/D1/.default/f.txt" in imported
    # Not in the extent, so not fetched.
    assert not (fresh / "data/D1/.default/process").exists()
    assert store.list() and store.list()[0].id.startswith("bench/1.0.0/")


def test_registry_is_read_only_so_a_write_cannot_reach_it(out_tree, tmp_path):
    _, snap_dir = _publish(out_tree, tmp_path / "registry")
    payload = snap_dir / "data/D1/.default/f.txt"
    assert payload.stat().st_mode & 0o777 == REGISTRY_MODE
    with pytest.raises(PermissionError):
        payload.open("w")


def test_publishing_leaves_the_working_tree_writable(out_tree, tmp_path):
    _publish(out_tree, tmp_path / "registry")
    (out_tree / "data/D1/.default/f.txt").open("a").close()


def test_descriptor_is_the_commit_point(out_tree, tmp_path):
    _, snap_dir = _publish(out_tree, tmp_path / "registry")
    store = LocalSnapshotStore(tmp_path / "registry")
    ref = str(snap_dir)

    # An interrupted publish is a payload with no descriptor: invisible, not
    # half-consumable.
    (snap_dir / DESCRIPTOR).unlink()
    assert store.list() == []
    with pytest.raises(FileNotFoundError):
        store.resolve(ref)


def test_republishing_needs_force(out_tree, tmp_path):
    with pytest.raises(FileExistsError):
        _publish(out_tree, tmp_path / "registry")
        _publish(out_tree, tmp_path / "registry")
    _publish(out_tree, tmp_path / "registry", force=True)


# --------------------------------------------------------------------------- integrity


def test_truncation_is_caught_without_reading_every_byte(out_tree, tmp_path):
    _, snap_dir = _publish(out_tree, tmp_path / "registry")
    payload = snap_dir / "data/D1/.default/f.txt"
    payload.chmod(0o644)
    payload.write_text("")

    with pytest.raises(SnapshotIntegrityError, match="expected"):
        verify(snap_dir, deep=False)


def test_silent_corruption_needs_the_deep_check(out_tree, tmp_path):
    _, snap_dir = _publish(out_tree, tmp_path / "registry")
    payload = snap_dir / "data/D1/.default/f.txt"
    original = payload.read_text()
    payload.chmod(0o644)
    payload.write_text("x" * len(original))  # same size, different bytes

    verify(snap_dir, deep=False)  # size-only cannot see this
    with pytest.raises(SnapshotIntegrityError, match="checksum"):
        verify(snap_dir, deep=True)


def test_a_tampered_manifest_is_caught_by_the_descriptor(out_tree, tmp_path):
    _, snap_dir = _publish(out_tree, tmp_path / "registry")
    (snap_dir / MANIFEST).write_text("f\tdata/D1/.default/f.txt\t0\tdeadbeef\n")
    with pytest.raises(SnapshotIntegrityError, match="MANIFEST"):
        verify(snap_dir, deep=False)


def test_materialise_refuses_a_broken_snapshot(out_tree, tmp_path):
    _, snap_dir = _publish(out_tree, tmp_path / "registry")
    payload = snap_dir / "data/D1/.default/f.txt"
    payload.chmod(0o644)
    payload.unlink()

    fresh = tmp_path / "fresh"
    with pytest.raises(SnapshotIntegrityError):
        materialize(snap_dir, fresh)
    # Verified before anything is linked, so nothing was half-populated.
    assert not fresh.exists() or not any(fresh.rglob("*.txt"))
