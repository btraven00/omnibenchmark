"""Append-only run log for output directories built by more than one run.

`manifest.json` describes the *latest* invocation and is rewritten each time
(007 §4.5). That is a state file, and it loses the history of a directory
assembled incrementally — resumed after a failure, extended with a new stage, or
built phase by phase on a cluster. This module adds the missing half: one
immutable line per invocation in `.metadata/runs.jsonl`.

Events, not state: there is nothing to reconcile between lines, so appending is
always correct (see scratch/incremental_manifest.md and design/012 §3.6).
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Iterable, Optional

RUNLOG = "runs.jsonl"
MANIFEST = "manifest.json"

# Host fields copied from the manifest into each run entry, so a comparability
# question can be answered from the log alone (012 §3.8).
HOST_FIELDS = (
    "hostname",
    "platform",
    "kernel",
    "cpu_count",
    "cpu_model",
    "memory_total_mb",
    "gpu_devices",
)

# What SLURM tells us about the allocation. The partition (plus any feature
# constraint) is the site's own statement that a set of nodes is
# interchangeable — a better hardware class than any string we could derive.
SLURM_VARS = {
    "cluster": "SLURM_CLUSTER_NAME",
    "job_id": "SLURM_JOB_ID",
    "partition": "SLURM_JOB_PARTITION",
    "constraint": "SLURM_JOB_CONSTRAINT",
    "nodelist": "SLURM_JOB_NODELIST",
    "cpus_per_node": "SLURM_JOB_CPUS_PER_NODE",
    "gpus": "SLURM_JOB_GPUS",
}


def slurm_allocation(env=None) -> Optional[Dict[str, str]]:
    """The current SLURM allocation, or None when not running under SLURM."""
    env = os.environ if env is None else env
    if not env.get("SLURM_JOB_ID"):
        return None
    return {
        name: env[var]
        for name, var in SLURM_VARS.items()
        if env.get(var) not in (None, "")
    }


def host_is_authoritative(snakemake_cmd: Optional[Iterable[str]]) -> bool:
    """Whether the recorded host is where the work actually ran.

    False when Snakemake dispatches jobs to other machines: the manifest then
    describes the submitting node — typically a login node with no GPUs — while
    the compute happens on workers whose hardware is never captured (007 §6).
    Recording that honestly beats reporting a confident wrong answer.
    """
    argv = list(snakemake_cmd or ())
    for i, arg in enumerate(argv):
        if arg == "--executor" and i + 1 < len(argv) and argv[i + 1] != "local":
            return False
        if arg.startswith("--executor=") and not arg.endswith("=local"):
            return False
    return True


def host_record(manifest: Optional[Dict] = None) -> Dict:
    """The comparability-relevant slice of a manifest (design/012 §3.8).

    One extractor for both the run log and the snapshot descriptor, so a
    snapshot's recorded hardware and its run's recorded hardware are the same
    shape and can be compared field for field.
    """
    manifest = manifest or {}
    return {
        "host": {field: manifest.get(field) for field in HOST_FIELDS},
        "slurm": manifest.get("slurm"),
        "host_authoritative": host_is_authoritative(manifest.get("snakemake_cmd")),
    }


def plan_hash(benchmark_yaml_path: Path) -> str:
    """Short content hash of a benchmark YAML, used to name its archived copy."""
    return hashlib.sha256(Path(benchmark_yaml_path).read_bytes()).hexdigest()[:8]


def append_run(
    output_dir: Path,
    *,
    plan: Optional[str] = None,
    starts_from: Iterable[str] = (),
    imported: int = 0,
    produced: Optional[Dict] = None,
    status: str = "ok",
) -> Dict:
    """Append one line describing this invocation to `.metadata/runs.jsonl`.

    Identity and host metadata are read back from `manifest.json` rather than
    re-collected, so the two records cannot disagree about the same run.

    ``starts_from`` holds snapshot ids, not file paths: which files came from a
    snapshot is already recorded in that snapshot's own MANIFEST, so repeating
    tens of thousands of paths in every log line would duplicate it at a cost
    that grows with the tree.
    """
    metadata_dir = Path(output_dir) / ".metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    manifest = {}
    manifest_path = metadata_dir / MANIFEST
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            # A damaged manifest must not cost us the run record.
            manifest = {}

    entry = {
        "run_id": manifest.get("run_id"),
        "timestamp": manifest.get("timestamp"),
        "ob_version": manifest.get("ob_version"),
        "plan": plan,
        "status": status,
        "starts_from": list(starts_from),
        "imported": imported,
        "produced": produced,
        **host_record(manifest),
    }
    with open(metadata_dir / RUNLOG, "a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def read_runs(output_dir: Path):
    """Every run entry, oldest first. Missing log means no runs recorded."""
    path = Path(output_dir) / ".metadata" / RUNLOG
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
