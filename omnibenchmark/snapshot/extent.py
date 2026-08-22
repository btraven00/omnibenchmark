"""What a snapshot covers, and how to read it off the output layout.

See docs/design/012-incremental-snapshots.md §3.1. An extent has two
coordinates: how far down the plan was computed (``stages``), and which branch
of it (``slice_by`` / ``slice_values``). Pure — no I/O.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Dict, FrozenSet, List, Optional, Tuple


@dataclass(frozen=True)
class Extent:
    """The set of nodes a snapshot covers.

    stages:       prefix-closed set of stage ids computed to completion.
    slice_by:     lineage label the horizontal cut is taken on. None = uncut.
    slice_values: values of that label included. Empty = every value.
    """

    stages: FrozenSet[str]
    slice_by: Optional[str] = None
    slice_values: FrozenSet[str] = field(default_factory=frozenset)

    def all_values(self) -> bool:
        """True when every branch is covered (uncut, or cut but unrestricted)."""
        return self.slice_by is None or not self.slice_values

    def covers(self, other: "Extent") -> bool:
        if not self.stages >= other.stages:
            return False
        if self.all_values():
            return True
        if other.all_values():
            return False
        if self.slice_by != other.slice_by:
            return False
        return self.slice_values >= other.slice_values

    def __or__(self, other: "Extent") -> "Extent":
        """Union. Used to check whether several runs together cover a plan."""
        if self.all_values() or other.all_values():
            slice_by = self.slice_by if other.all_values() else other.slice_by
            return Extent(self.stages | other.stages, slice_by, frozenset())
        if self.slice_by != other.slice_by:
            raise ValueError(
                f"cannot union extents cut on different labels: "
                f"{self.slice_by!r} vs {other.slice_by!r}"
            )
        return Extent(
            self.stages | other.stages,
            self.slice_by,
            self.slice_values | other.slice_values,
        )

    # ponytail: no __and__/__sub__ until delta benchmarking needs them (012 §3.9).

    def key(self) -> str:
        """Stable 8-char id, independent of member ordering."""
        blob = json.dumps(self.to_dict(), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:8]

    def to_dict(self) -> Dict:
        return {
            "stages": sorted(self.stages),
            "slice_by": self.slice_by,
            "slice_values": sorted(self.slice_values),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Extent":
        return cls(
            frozenset(d["stages"]),
            d.get("slice_by"),
            frozenset(d.get("slice_values") or ()),
        )


def lineage(rel_path) -> List[Tuple[str, str]]:
    """Decode a nested output path into its ``(stage_id, module_id)`` chain.

    The layout is repeated ``<stage>/<module>/.<param_hash>/`` triples (007 §3),
    so the chain is read directly off the path with no resolution step. Parsing
    stops at the first segment that is not a param-hash directory, which is
    where module-internal subdirectories begin.
    """
    parts = PurePosixPath(rel_path).parts
    out: List[Tuple[str, str]] = []
    i = 0
    while i + 2 < len(parts) and parts[i + 2].startswith("."):
        out.append((parts[i], parts[i + 1]))
        i += 3
    return out
    # ponytail: a module writing its own dot-prefixed subdirectory would be
    # misread as a param-hash dir. Resolve against resolved_nodes if it happens.


def slice_value(
    chain: List[Tuple[str, str]], label_stage: Optional[str]
) -> Optional[str]:
    """The branch a node belongs to: the module chosen at *label_stage*.

    None means the node sits above the labelling stage — it is trunk, shared by
    every branch (012 §3.1).
    """
    if label_stage is None:
        return None
    for stage_id, module_id in chain:
        if stage_id == label_stage:
            return module_id
    return None
