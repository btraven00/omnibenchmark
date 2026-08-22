"""Incremental snapshots — slicing an output tree and reusing it by hardlink.

Represents: a *part* of a benchmark run (a stage cut, a dataset branch, or
both), named so it can be published, fetched and materialised into another
working directory without recomputation.
Layer: orchestration. Depends on: core, storage.
Design: docs/design/012-incremental-snapshots.md
"""

from .compat import Problem, check, hardware_class, is_compatible, prefix_hash
from .extent import Extent, lineage, slice_value
from .link import place, select
from .store import (
    DEFAULT_REGISTRY,
    LocalSnapshotStore,
    Snapshot,
    SnapshotIntegrityError,
    materialize,
    verify,
)

__all__ = [
    "Extent",
    "Problem",
    "check",
    "hardware_class",
    "is_compatible",
    "prefix_hash",
    "lineage",
    "slice_value",
    "select",
    "place",
    "Snapshot",
    "LocalSnapshotStore",
    "SnapshotIntegrityError",
    "materialize",
    "verify",
    "DEFAULT_REGISTRY",
]
