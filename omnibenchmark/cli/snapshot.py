"""cli commands for incremental snapshots (docs/design/012-incremental-snapshots.md)."""

import sys
from pathlib import Path

import click

from omnibenchmark.logging import logger
from omnibenchmark.snapshot import (
    DEFAULT_REGISTRY,
    Extent,
    LocalSnapshotStore,
    Snapshot,
    SnapshotIntegrityError,
    select,
    verify as verify_snapshot,
)
from omnibenchmark.snapshot.plan import BUILTIN_LABEL, label_stage, stage_closure

registry_option = click.option(
    "--registry",
    type=click.Path(path_type=Path),
    default=DEFAULT_REGISTRY,
    show_default=True,
    help="Snapshot registry directory. Must be on the same volume as the output "
    "directory, since materialising a snapshot uses hardlinks.",
)


def _load_model(benchmark: str):
    from omnibenchmark.model import Benchmark as BenchmarkModel

    try:
        return BenchmarkModel.from_yaml(Path(benchmark))
    except Exception as e:
        logger.error(f"Failed to load benchmark: {e}")
        sys.exit(1)


@click.group(name="snapshot")
def snapshot():
    """Publish and reuse slices of a benchmark output tree."""


@snapshot.command(name="push")
@click.argument("benchmark", type=click.Path(exists=True))
@click.option("--until", "until_stage", required=True, help="Last stage to include.")
@click.option(
    "--slice-by",
    default=BUILTIN_LABEL,
    show_default=True,
    help="Lineage label the horizontal cut follows.",
)
@click.option(
    "--only",
    "only_values",
    multiple=True,
    metavar="VALUE",
    help="Publish only these branches of --slice-by (repeatable). Default: all.",
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("out"),
    show_default=True,
    help="Output directory to slice.",
)
@click.option("--force", is_flag=True, help="Replace an already-published snapshot.")
@registry_option
def push(benchmark, until_stage, slice_by, only_values, out_dir, registry, force):
    """Publish the slice of OUT-DIR up to --until into the registry."""
    model = _load_model(benchmark)
    try:
        stages = stage_closure(model, until_stage)
        binding_stage = label_stage(model, slice_by)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    extent = Extent(stages, slice_by, frozenset(only_values))
    files, links = select(out_dir, extent, binding_stage)
    if not files:
        logger.error(
            f"nothing to publish: no outputs under {out_dir} match stages "
            f"{', '.join(sorted(stages))}. Has the benchmark been run?"
        )
        sys.exit(1)

    snap = Snapshot(
        benchmark_id=model.get_name(),
        version=model.get_version(),
        extent=extent,
        label_stage=binding_stage,
        ob_version=_ob_version(),
        n_files=len(files),
    )
    try:
        dest = LocalSnapshotStore(registry).push(
            snap, out_dir, files, links, force=force
        )
    except FileExistsError as e:
        logger.error(str(e))
        sys.exit(1)
    click.echo(f"{snap.id}  {len(files)} files, {len(links)} links  -> {dest}")


@snapshot.command(name="list")
@registry_option
def list_snapshots(registry):
    """List snapshots in the registry."""
    snaps = LocalSnapshotStore(registry).list()
    if not snaps:
        click.echo(f"No snapshots in {registry}.")
        return
    for snap in snaps:
        cut = ", ".join(sorted(snap.extent.stages))
        branches = (
            "all"
            if snap.extent.all_values()
            else ", ".join(sorted(snap.extent.slice_values))
        )
        click.echo(
            f"{snap.id}  stages=[{cut}]  {snap.extent.slice_by}=[{branches}]  {snap.n_files} files"
        )


@snapshot.command(name="verify")
@click.argument("ref")
@click.option(
    "--shallow",
    is_flag=True,
    help="Check presence and size only, without re-reading every byte.",
)
@registry_option
def verify_cmd(ref, shallow, registry):
    """Check a snapshot's payload against its descriptor."""
    store = LocalSnapshotStore(registry)
    try:
        snap_dir = store.resolve(ref)
        verify_snapshot(snap_dir, deep=not shallow)
    except (FileNotFoundError, SnapshotIntegrityError) as e:
        logger.error(str(e))
        sys.exit(1)
    snap = store.load(snap_dir)
    click.echo(f"{snap.id}: ok ({snap.n_files} files)")


def _ob_version():
    try:
        from importlib.metadata import version

        return version("omnibenchmark")
    except Exception:
        return None
