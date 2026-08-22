"""Reading an Extent out of a benchmark plan.

Kept apart from :mod:`extent`, which stays pure. See 012 §3.1/§3.2.
"""

from collections import defaultdict
from typing import FrozenSet, Optional

from omnibenchmark.core._graph import build_stage_dag

# The runtime auto-populates this label for entrypoint nodes; it is the only
# one available without Stage.provides (008 phase 2 / PR #354).
BUILTIN_LABEL = "dataset"


def stage_closure(model, until: str) -> FrozenSet[str]:
    """*until* plus every stage feeding it, transitively.

    Selection is by declared lineage, not declaration order: a benchmark may
    declare an ancestor after its consumer.
    """
    stages = model.get_stages()
    if until not in stages:
        raise ValueError(
            f"stage '{until}' not found. Available stages: {', '.join(stages)}"
        )
    parents = defaultdict(set)
    for upstream, downstream in build_stage_dag(model).edges:
        parents[downstream].add(upstream)

    keep = {until}
    queue = [until]
    while queue:
        for up in parents.get(queue.pop(), ()):
            if up not in keep:
                keep.add(up)
                queue.append(up)
    return frozenset(keep)


def label_stage(model, label: str = BUILTIN_LABEL) -> Optional[str]:
    """The stage that binds *label*, i.e. where the horizontal cut is taken.

    Phase 1 supports only the builtin ``dataset`` label, which the runtime binds
    at the entrypoint stage. Declared ``Stage.provides`` labels widen this once
    PR #354 lands; until then, asking for one is an error rather than a silent
    no-op.
    """
    declared = [
        stage.id
        for stage in model.stages
        if label in (getattr(stage, "provides", None) or ())
    ]
    if declared:
        return declared[-1]
    if label != BUILTIN_LABEL:
        raise ValueError(
            f"no stage declares the label '{label}'. Declaring one needs "
            f"`Stage.provides` (api_version >= 0.6.0); the builtin "
            f"'{BUILTIN_LABEL}' label is always available."
        )

    dag = build_stage_dag(model)
    roots = [stage_id for stage_id, degree in dag.in_degree() if degree == 0]
    if len(roots) != 1:
        raise ValueError(
            f"the builtin '{BUILTIN_LABEL}' label needs a single entrypoint "
            f"stage to bind at, but this benchmark has {len(roots)}: "
            f"{', '.join(sorted(roots))}. Declare `provides: [{BUILTIN_LABEL}]` "
            "on the stage the slice should follow."
        )
    return roots[0]
