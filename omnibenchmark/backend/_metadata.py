"""
Benchmark metadata persistence.

Writes human-readable metadata files alongside the generated Snakefile so
that the output directory is self-documenting without requiring omnibenchmark
to be installed.
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from omnibenchmark.backend._runlog import plan_hash
from omnibenchmark.model.resolved import ResolvedNode


def save_metadata(
    benchmark_yaml_path: Path,
    output_dir: Path,
    nodes: List[ResolvedNode],
) -> str:
    """
    Save benchmark metadata to the output directory.

    Creates:
    - out/.metadata/benchmark.yaml         (copy of the original benchmark YAML)
    - out/.metadata/benchmark-<sha8>.yaml  (same copy, content-addressed)
    - out/.metadata/modules.txt            (unique modules with URLs and commits)

    The content-addressed copy is what makes an incrementally built output
    directory auditable. `benchmark.yaml` is overwritten by every run, so if the
    plan is edited between runs the earlier one is destroyed while outputs
    produced under it remain in the tree. Keeping a copy per distinct plan costs
    nothing when the plan is unchanged — same hash, same file — and preserves
    the evidence when it is not.

    Returns the plan hash, for the run log to reference.
    """
    metadata_dir = output_dir / ".metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy(benchmark_yaml_path, metadata_dir / "benchmark.yaml")
    digest = plan_hash(benchmark_yaml_path)
    shutil.copy(benchmark_yaml_path, metadata_dir / f"benchmark-{digest}.yaml")

    with open(metadata_dir / "modules.txt", "w") as f:
        f.write("# Modules used in this benchmark\n")
        f.write(f"# Generated: {datetime.now()}\n")
        f.write("#\n")
        f.write("# Format: stage/module - repository@commit\n")
        f.write("#\n\n")

        seen_modules: set = set()
        for node in nodes:
            module_key = (node.module.repository_url, node.module.commit)
            if module_key not in seen_modules:
                seen_modules.add(module_key)
                f.write(f"{node.stage_id}/{node.module_id}:\n")
                f.write(f"  Repository: {node.module.repository_url}\n")
                f.write(f"  Commit: {node.module.commit}\n")
                f.write(f"  Module dir: {node.module.module_dir}\n")
                f.write(f"  Entrypoint: {node.module.entrypoint}\n")
                f.write("\n")

    return digest
