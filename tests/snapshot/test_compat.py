"""Phase 3 of design/012: may this snapshot be used here?"""

import pytest

from omnibenchmark.model import Benchmark as BenchmarkModel
from omnibenchmark.snapshot import Extent, Snapshot
from omnibenchmark.snapshot.compat import (
    check,
    hardware_class,
    is_compatible,
    prefix_hash,
)

YAML = """
id: bench
version: "{version}"
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
        repository:
          url: https://example.org/data.git
          commit: aaaaaaa
    outputs:
      - id: data.matrix
        path: "matrix.csv"
  - id: methods
    modules:
      - id: M1
        software_environment: py
        {capabilities}repository:
          url: https://example.org/m1.git
          commit: {commit}
    inputs: [data.matrix]
    outputs:
      - id: methods.out
        path: "out.csv"
"""


def model(version="1.0.0", commit="bbbbbbb", capabilities=""):
    return BenchmarkModel.from_yaml(
        YAML.format(version=version, commit=commit, capabilities=capabilities)
    )


def snap(version="1.0.0", stages=("data",), **kw):
    return Snapshot("bench", version, Extent(frozenset(stages)), **kw)


# ------------------------------------------------------------------- versioning


@pytest.mark.parametrize(
    "snapshot_version, plan_version, ok",
    [
        ("1.0.0", "1.0.0", True),
        ("1.0.0", "1.0.9", True),  # patch: changes below the cut only
        ("1.0.0", "1.1.0", False),  # minor: the plan changed at or above the cut
        ("1.0.0", "2.0.0", False),
        ("1.2.0", "1.1.0", False),
    ],
)
def test_compatibility_is_major_minor_equality(snapshot_version, plan_version, ok):
    assert is_compatible(snap(snapshot_version), plan_version) is ok


def test_unparseable_versions_fall_back_to_equality():
    assert is_compatible(snap("nightly"), "nightly")
    assert not is_compatible(snap("nightly"), "1.0.0")


# ------------------------------------------------------------------ prefix hash


def test_prefix_hash_ignores_changes_below_the_cut():
    # Repointing the methods module is exactly the edit a patch bump describes.
    before = prefix_hash(model(commit="bbbbbbb"), frozenset({"data"}))
    after = prefix_hash(model(commit="ccccccc"), frozenset({"data"}))
    assert before == after


def test_prefix_hash_changes_when_the_covered_stages_change():
    narrow = prefix_hash(model(), frozenset({"data"}))
    wide = prefix_hash(model(), frozenset({"data", "methods"}))
    assert narrow != wide


def test_version_is_the_gate_and_the_prefix_hash_only_warns():
    plan = model()
    stale = snap(prefix_hash="0" * 16)
    problems = check(stale, plan)
    assert [p.level for p in problems] == ["warning"]
    assert "without a minor version bump" in problems[0].message


def test_an_incompatible_version_is_an_error():
    problems = check(snap("1.0.0"), model(version="1.1.0"))
    assert any(p.is_error for p in problems)


def test_a_snapshot_without_a_prefix_hash_skips_that_check():
    # Published before the gate existed: nothing to compare against.
    assert check(snap(prefix_hash=None), model()) == []


# --------------------------------------------------------------------- hardware


def test_slurm_partition_beats_cpu_strings():
    a = {"slurm": {"cluster": "euler", "partition": "gpu", "constraint": "a100"}}
    b = {
        "slurm": {"cluster": "euler", "partition": "gpu", "constraint": "a100"},
        "host": {"cpu_model": "a different cpu"},
    }
    assert hardware_class(a) == hardware_class(b)

    other = {"slurm": {"cluster": "euler", "partition": "cpu"}}
    assert hardware_class(a) != hardware_class(other)


def test_without_slurm_the_class_is_cpu_and_gpus():
    a = {"host": {"cpu_model": "Ryzen", "gpu_devices": [{"name": "A100"}]}}
    b = {"host": {"cpu_model": "Ryzen", "gpu_devices": [{"name": "H100"}]}}
    assert hardware_class(a) != hardware_class(b)
    assert hardware_class(a) == hardware_class(
        {"host": {"cpu_model": "Ryzen", "gpu_devices": [{"name": "A100"}]}}
    )


HERE = {"host": {"cpu_model": "Ryzen", "gpu_devices": None}, "host_authoritative": True}
THERE = {"host": {"cpu_model": "Xeon", "gpu_devices": None}, "host_authoritative": True}


def test_mixed_hardware_only_warns_when_no_module_declares_a_capability():
    problems = check(snap(host=THERE, stages=("data",)), model(), here=HERE)
    assert [p.level for p in problems] == ["warning"]
    assert "results should not" in problems[0].message


def test_mixed_hardware_is_an_error_where_a_capability_is_declared():
    plan = model(capabilities="requires_capabilities: [gpu]\n        ")
    covering_methods = snap(host=THERE, stages=("data", "methods"))
    problems = check(covering_methods, plan, here=HERE)
    assert any(p.is_error for p in problems)
    assert "--allow-mixed-hardware" in problems[0].message


def test_matching_hardware_says_nothing():
    assert check(snap(host=HERE), model(), here=HERE) == []


def test_a_non_authoritative_host_record_is_flagged():
    submitted = {**THERE, "host_authoritative": False}
    problems = check(snap(host=submitted), model(), here=HERE)
    assert any("submitted its run" in p.message for p in problems)
    assert not any(p.is_error for p in problems)


def test_hardware_is_described_in_the_terms_it_was_classified_by():
    from omnibenchmark.snapshot.compat import _describe, hardware_class

    slurm = hardware_class(
        {"slurm": {"cluster": "euler", "partition": "gpu", "constraint": "a100"}}
    )
    assert _describe(slurm) == "euler/gpu/a100"
    assert _describe(("slurm", None, None, None)) == "slurm"

    host = hardware_class(
        {"host": {"cpu_model": "Ryzen", "gpu_devices": [{"name": "A100"}]}}
    )
    assert _describe(host) == "Ryzen + A100"
    assert _describe(hardware_class({})) == "unknown cpu"
