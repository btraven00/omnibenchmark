"""Consuming part of a source: --after and --filter, published or local."""

import pytest

from omnibenchmark.snapshot import Extent, LocalSnapshotStore, Snapshot, select
from omnibenchmark.snapshot.plan import parse_filters
from omnibenchmark.snapshot.store import materialize, materialize_tree, snapshot_of_tree

PLAN = """
id: bench
version: "1.0.0"
benchmarker: tester
api_version: "0.3.0"
software_backend: host
software_environments:
  py:
    description: python
    conda: envs/py.yaml
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
def published(tmp_path):
    """A snapshot covering two stages and two branches."""
    out = tmp_path / "out"
    for rel in [
        "data/D1/.default/f.txt",
        "data/D2/.default/f.txt",
        "data/D1/.default/process/P1/.abc/g.txt",
        "data/D2/.default/process/P1/.abc/g.txt",
    ]:
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(rel)

    extent = Extent(frozenset({"data", "process"}), "dataset", frozenset())
    files, links = select(out, extent, "data")
    snap = Snapshot("bench", "1.0.0", extent, label_stage="data", n_files=len(files))
    store = LocalSnapshotStore(tmp_path / "reg")
    return store.push(snap, out, files, links)


# ----------------------------------------------------------------- --filter


def test_filter_parses_stage_and_value():
    assert parse_filters(["data:iris"]) == ("data", frozenset({"iris"}))


def test_repeating_filter_unions_branches_on_one_axis():
    axis, values = parse_filters(["data:iris", "data:penguins"])
    assert axis == "data" and values == {"iris", "penguins"}


@pytest.mark.parametrize("spec", ["iris", "data:", ":iris", ""])
def test_malformed_filters_say_what_was_expected(spec):
    with pytest.raises(ValueError, match="STAGE:VALUE"):
        parse_filters([spec])


def test_two_axes_are_rejected_because_an_extent_has_one():
    with pytest.raises(ValueError, match="one axis at a time"):
        parse_filters(["data:iris", "cohort:healthy"])


def test_filtering_on_the_wrong_axis_names_the_right_one():
    snap = Snapshot(
        "b", "1.0.0", Extent(frozenset({"data"}), "dataset"), label_stage="data"
    )
    with pytest.raises(ValueError, match="cut at"):
        parse_filters(["samples:healthy"], snapshot=snap)


# -------------------------------------------------------- narrowed materialise


def test_after_takes_only_the_upstream_stages(published, tmp_path):
    want = Extent(frozenset({"data"}), "dataset", frozenset())
    got = materialize(published, tmp_path / "w", want=want)
    assert got == ["data/D1/.default/f.txt", "data/D2/.default/f.txt"]
    assert not (tmp_path / "w/data/D1/.default/process").exists()


def test_filter_takes_only_one_branch(published, tmp_path):
    want = Extent(frozenset({"data", "process"}), "dataset", frozenset({"D1"}))
    got = materialize(published, tmp_path / "w", want=want)
    assert all("/D1/" in rel for rel in got)
    assert len(got) == 2


def test_both_narrowings_compose(published, tmp_path):
    want = Extent(frozenset({"data"}), "dataset", frozenset({"D1"}))
    assert materialize(published, tmp_path / "w", want=want) == [
        "data/D1/.default/f.txt"
    ]


def test_no_narrowing_takes_everything(published, tmp_path):
    assert len(materialize(published, tmp_path / "w")) == 4


def test_a_source_that_does_not_reach_far_enough_is_detectable(published):
    snap = LocalSnapshotStore.load(published)
    assert not snap.extent.covers(Extent(frozenset({"data", "process", "methods"})))
    assert snap.extent.covers(Extent(frozenset({"data"})))


# ------------------------------------------------------------- local base tree


@pytest.fixture
def base_tree(tmp_path):
    out = tmp_path / "prev"
    (out / ".metadata").mkdir(parents=True)
    (out / ".metadata" / "benchmark.yaml").write_text(PLAN)
    (out / ".metadata" / "manifest.json").write_text(
        '{"hostname": "node7", "cpu_model": "Ryzen", "slurm": null}'
    )
    for rel in ["data/D1/.default/f.txt", "data/D2/.default/f.txt"]:
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(rel)
    return out


def test_an_output_tree_describes_itself(base_tree):
    snap = snapshot_of_tree(base_tree, Extent(frozenset({"data"}), "dataset"), "data")
    assert snap.benchmark_id == "bench" and snap.version == "1.0.0"
    assert snap.host["host"]["cpu_model"] == "Ryzen"
    assert snap.prefix_hash  # the gate has everything it needs
    assert snap.source == "local" and not snap.reproducible
    assert snap.id.startswith("local:")


def test_a_directory_that_was_never_run_is_refused(tmp_path):
    with pytest.raises(FileNotFoundError, match="neither a published snapshot"):
        snapshot_of_tree(tmp_path, Extent(frozenset({"data"})), "data")


def test_a_local_base_narrows_like_a_published_one(base_tree, tmp_path):
    want = Extent(frozenset({"data"}), "dataset", frozenset({"D1"}))
    snap = snapshot_of_tree(base_tree, want, "data")
    got = materialize_tree(base_tree, tmp_path / "w", snap, want)
    assert got == ["data/D1/.default/f.txt"]
    assert (tmp_path / "w/data/D1/.default/f.txt").stat().st_nlink == 2
