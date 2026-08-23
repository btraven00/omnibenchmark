"""Phase 2 of design/012: the append-only run log and host capture."""

import json

import pytest

from omnibenchmark.backend._manifest import write_run_manifest
from omnibenchmark.backend._runlog import (
    append_run,
    host_is_authoritative,
    plan_hash,
    read_runs,
    slurm_allocation,
)


# ------------------------------------------------------------------ host capture


def test_slurm_allocation_is_none_outside_a_job():
    assert slurm_allocation({"HOME": "/home/x"}) is None


def test_slurm_allocation_records_the_hardware_class():
    alloc = slurm_allocation(
        {
            "SLURM_JOB_ID": "42",
            "SLURM_JOB_PARTITION": "gpu",
            "SLURM_JOB_CONSTRAINT": "a100",
            "SLURM_CLUSTER_NAME": "euler",
            "SLURM_JOB_GPUS": "",  # unset-but-present must not become a field
        }
    )
    assert alloc == {
        "job_id": "42",
        "partition": "gpu",
        "constraint": "a100",
        "cluster": "euler",
    }


@pytest.mark.parametrize(
    "cmd, authoritative",
    [
        (["snakemake", "--cores", "8"], True),
        (["snakemake", "--executor", "local"], True),
        (["snakemake", "--executor", "slurm"], False),
        (["snakemake", "--executor=slurm"], False),
        (None, True),
    ],
)
def test_host_is_authoritative_only_when_work_runs_here(cmd, authoritative):
    assert host_is_authoritative(cmd) is authoritative


# ---------------------------------------------------------------------- run log


def test_a_run_entry_reuses_the_manifest_identity(tmp_path):
    manifest = write_run_manifest(output_dir=tmp_path)
    entry = append_run(tmp_path, plan="abc12345", produced={"stages": ["data"]})

    assert entry["run_id"] == manifest["run_id"]
    assert entry["host"]["hostname"] == manifest["hostname"]
    assert entry["host_authoritative"] is True
    assert entry["plan"] == "abc12345"
    assert entry["status"] == "ok"


def test_entries_accumulate_rather_than_replace(tmp_path):
    write_run_manifest(output_dir=tmp_path)
    append_run(tmp_path, plan="aaaaaaaa", status="failed")
    append_run(tmp_path, plan="bbbbbbbb", starts_from=["b/1.0/deadbeef"], imported=16)

    runs = read_runs(tmp_path)
    assert [r["plan"] for r in runs] == ["aaaaaaaa", "bbbbbbbb"]
    assert runs[0]["status"] == "failed"
    assert runs[1]["starts_from"] == ["b/1.0/deadbeef"]
    assert runs[1]["imported"] == 16


def test_the_log_survives_a_damaged_manifest(tmp_path):
    (tmp_path / ".metadata").mkdir()
    (tmp_path / ".metadata" / "manifest.json").write_text("{not json")
    entry = append_run(tmp_path, plan="abc12345")
    assert entry["run_id"] is None and entry["plan"] == "abc12345"


def test_manifest_records_the_slurm_allocation(tmp_path, monkeypatch):
    monkeypatch.setenv("SLURM_JOB_ID", "7")
    monkeypatch.setenv("SLURM_JOB_PARTITION", "gpu")
    write_run_manifest(output_dir=tmp_path)
    manifest = json.loads((tmp_path / ".metadata" / "manifest.json").read_text())
    assert manifest["slurm"]["partition"] == "gpu"

    append_run(tmp_path)
    assert read_runs(tmp_path)[0]["slurm"]["partition"] == "gpu"


# ------------------------------------------------------------------- plan copies


def test_plan_hash_is_content_addressed(tmp_path):
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_text("id: bench\n")
    b.write_text("id: bench\n")
    assert plan_hash(a) == plan_hash(b)
    b.write_text("id: other\n")
    assert plan_hash(a) != plan_hash(b)


def test_editing_the_plan_does_not_destroy_the_previous_copy(tmp_path):
    from omnibenchmark.backend._metadata import save_metadata

    plan = tmp_path / "bench.yaml"
    out = tmp_path / "out"

    plan.write_text("id: v1\n")
    first = save_metadata(plan, out, nodes=[])
    plan.write_text("id: v2\n")
    second = save_metadata(plan, out, nodes=[])

    assert first != second
    # Both plans that produced outputs in this tree are still on disk.
    assert (out / ".metadata" / f"benchmark-{first}.yaml").read_text() == "id: v1\n"
    assert (out / ".metadata" / f"benchmark-{second}.yaml").read_text() == "id: v2\n"
    assert (out / ".metadata" / "benchmark.yaml").read_text() == "id: v2\n"


def test_a_run_is_recorded_even_with_no_manifest_at_all(tmp_path):
    # write_run_manifest has not run: the entry is thinner, never absent.
    entry = append_run(tmp_path, plan="abc12345", status="failed")
    assert entry["run_id"] is None and entry["status"] == "failed"
    assert entry["host"]["hostname"] is None
    assert read_runs(tmp_path)[0]["plan"] == "abc12345"
