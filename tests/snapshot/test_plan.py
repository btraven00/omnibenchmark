"""Reading an extent out of a plan: stage closure and label binding."""

import pytest

from omnibenchmark.model import Benchmark as BenchmarkModel
from omnibenchmark.snapshot.plan import BUILTIN_LABEL, label_stage, stage_closure

HEAD = """
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
"""


def stage(sid, outputs, inputs=None):
    block = f"""  - id: {sid}
    modules:
      - id: {sid.upper()}1
        software_environment: py
        repository: {{url: https://example.org/{sid}.git, commit: aaaaaaa}}
"""
    if inputs:
        block += f"    inputs: [{', '.join(inputs)}]\n"
    block += "    outputs:\n"
    for out in outputs:
        block += f'      - {{id: {out}, path: "{out.replace(".", "_")}.csv"}}\n'
    return block


def model(*stages):
    return BenchmarkModel.from_yaml(HEAD + "".join(stages))


# ------------------------------------------------------------------ closure


@pytest.fixture
def chain():
    """data -> process -> methods, plus an unrelated branch off data."""
    return model(
        stage("data", ["data.matrix"]),
        stage("process", ["process.out"], ["data.matrix"]),
        stage("methods", ["methods.out"], ["process.out"]),
        stage("qc", ["qc.out"], ["data.matrix"]),
    )


def test_closure_of_an_entrypoint_is_itself(chain):
    assert stage_closure(chain, "data") == {"data"}


def test_closure_pulls_in_transitive_ancestors(chain):
    assert stage_closure(chain, "methods") == {"data", "process", "methods"}


def test_closure_excludes_siblings_and_descendants(chain):
    # qc also consumes data, but is not upstream of process.
    assert stage_closure(chain, "process") == {"data", "process"}


def test_closure_follows_lineage_not_declaration_order():
    # The ancestor is declared *after* its consumer; order must not matter.
    out_of_order = model(
        stage("methods", ["methods.out"], ["data.matrix"]),
        stage("data", ["data.matrix"]),
    )
    assert stage_closure(out_of_order, "methods") == {"data", "methods"}
    assert stage_closure(out_of_order, "data") == {"data"}


def test_closure_is_prefix_closed(chain):
    """Every stage kept has all of its own ancestors kept too."""
    kept = stage_closure(chain, "methods")
    for sid in kept:
        assert stage_closure(chain, sid) <= kept


def test_an_unknown_stage_lists_the_real_ones(chain):
    with pytest.raises(ValueError, match="not found. Available stages"):
        stage_closure(chain, "nope")


# ------------------------------------------------------------ label binding


def test_the_builtin_label_binds_at_the_only_entrypoint(chain):
    assert label_stage(chain, BUILTIN_LABEL) == "data"
    assert label_stage(chain) == "data"  # dataset is the default


def test_several_entrypoints_are_ambiguous_and_say_how_to_fix_it():
    two_roots = model(
        stage("dataA", ["a.matrix"]),
        stage("dataB", ["b.matrix"]),
        stage("methods", ["m.out"], ["a.matrix", "b.matrix"]),
    )
    with pytest.raises(ValueError, match="single entrypoint"):
        label_stage(two_roots)


def test_an_undeclared_label_points_at_the_feature_that_declares_it(chain):
    with pytest.raises(ValueError, match="Stage.provides"):
        label_stage(chain, "cohort")


def test_a_declared_label_binds_at_its_stage(chain):
    # `Stage.provides` lands with PR #354; the lookup already honours it, so
    # the forward path is pinned here rather than left to discover later.
    for st in chain.stages:
        st.__dict__["provides"] = ["cohort"] if st.id == "process" else None
    assert label_stage(chain, "cohort") == "process"


def test_the_downstream_declaration_wins_when_two_stages_advertise_one_label(chain):
    for st in chain.stages:
        st.__dict__["provides"] = ["cohort"] if st.id in ("data", "process") else None
    assert label_stage(chain, "cohort") == "process"


def test_a_diamond_visits_a_shared_ancestor_once():
    # data feeds two stages that both feed merge; the closure must terminate
    # and list the shared ancestor once.
    diamond = model(
        stage("data", ["data.matrix"]),
        stage("left", ["left.out"], ["data.matrix"]),
        stage("right", ["right.out"], ["data.matrix"]),
        stage("merge", ["merge.out"], ["left.out", "right.out"]),
    )
    assert stage_closure(diamond, "merge") == {"data", "left", "right", "merge"}


def test_a_filter_on_the_source_own_axis_is_accepted():
    from omnibenchmark.snapshot import Extent, Snapshot
    from omnibenchmark.snapshot.plan import parse_filters

    snap = Snapshot(
        "b", "1.0.0", Extent(frozenset({"data"}), "dataset"), label_stage="data"
    )
    assert parse_filters(["data:iris"], snapshot=snap) == ("data", frozenset({"iris"}))
    # the label it advertises names the same axis
    assert parse_filters(["dataset:iris"], snapshot=snap)[1] == frozenset({"iris"})
