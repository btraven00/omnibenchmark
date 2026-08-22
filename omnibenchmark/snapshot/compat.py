"""May this snapshot be used here?

Two independent questions, answered separately because they fail differently
(design/012 §3.2 and §3.8):

  * **Compatibility** — was the snapshot produced by a plan close enough to this
    one that its outputs are still the right answer? Gated on the declared
    benchmark version.
  * **Comparability** — was it produced on hardware close enough that the
    numbers may be compared? Gated on the hardware class, and only where a
    module says it cares.

Nothing here reads the payload; it compares records.
"""

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Tuple

from packaging.version import InvalidVersion, Version

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Problem:
    level: str
    message: str

    @property
    def is_error(self) -> bool:
        return self.level == ERROR


# --------------------------------------------------------------------- the plan


def prefix_hash(model, stages: FrozenSet[str]) -> str:
    """``summary_hash()`` restricted to the stages a snapshot covers.

    Delegates to the model's own canonicalisation rather than re-deriving it, so
    the two hashes cannot drift apart. Metric collectors are dropped (they are
    downstream of any cut by definition) and software environments are narrowed
    to those the kept modules actually reference, so an edit below the cut does
    not change the hash above it.
    """
    kept = [stage for stage in model.stages if stage.id in stages]
    used = {
        module.software_environment
        for stage in kept
        for module in stage.modules
        if module.software_environment
    }
    narrowed = model.model_copy(
        update={
            "stages": kept,
            "metric_collectors": None,
            "software_environments": [
                env for env in model.software_environments if env.id in used
            ],
        }
    )
    return narrowed.summary_hash()[:16]


def is_compatible(snapshot, plan_version: str) -> bool:
    """Whether *snapshot* may seed a plan at *plan_version*.

    Same major and minor: the author's promise is that everything at or above
    the cut is unchanged, and only patch-level edits happened below it. Adding a
    branch to the labelling stage is a patch bump too, so a snapshot covering
    three datasets stays usable when a fourth is added — the fourth simply
    computes from scratch.
    """
    try:
        a, b = Version(snapshot.version), Version(plan_version)
    except InvalidVersion:
        return snapshot.version == plan_version
    return (a.major, a.minor) == (b.major, b.minor)


# ----------------------------------------------------------------- the hardware


def hardware_class(record: Optional[Dict]) -> Tuple:
    """The equivalence class of the machine a run happened on.

    Under SLURM this is the site's own answer: a partition (with any feature
    constraint) is a cluster stating that a set of nodes is interchangeable.
    That beats comparing CPU model strings, which are simultaneously too strict
    (a stepping is not a comparability difference) and too loose (same model,
    different clock cap), and which say nothing about accelerators.
    """
    record = record or {}
    slurm = record.get("slurm")
    if slurm:
        return (
            "slurm",
            slurm.get("cluster"),
            slurm.get("partition"),
            slurm.get("constraint"),
        )
    host = record.get("host") or {}
    gpus = tuple(sorted(g.get("name") for g in (host.get("gpu_devices") or ())))
    return ("host", host.get("cpu_model"), gpus)


def _hardware_sensitive_stages(model, stages: FrozenSet[str]) -> List[str]:
    """Stages a module has explicitly marked as caring about the host."""
    return sorted(
        stage.id
        for stage in model.stages
        if stage.id in stages
        and any(module.requires_capabilities for module in stage.modules)
    )


def _describe(cls: Tuple) -> str:
    if cls[0] == "slurm":
        return "/".join(str(part) for part in cls[1:] if part) or "slurm"
    cpu, gpus = cls[1], cls[2]
    return f"{cpu or 'unknown cpu'}" + (f" + {', '.join(gpus)}" if gpus else "")


# ------------------------------------------------------------------- the verdict


def check(snapshot, model, here: Optional[Dict] = None) -> List[Problem]:
    """Everything wrong with using *snapshot* to seed *model* on this machine.

    Errors block; warnings are reported and the run continues. Ordered most
    serious first.
    """
    problems: List[Problem] = []

    if not is_compatible(snapshot, model.get_version()):
        problems.append(
            Problem(
                ERROR,
                f"snapshot was produced at version {snapshot.version}, but this "
                f"plan declares {model.get_version()}. A minor or major bump "
                "means the plan changed at or above the cut, so the snapshot's "
                "outputs are no longer the right answer. Re-publish the "
                "snapshot from a run of this plan.",
            )
        )

    expected = prefix_hash(model, snapshot.extent.stages)
    if snapshot.prefix_hash and snapshot.prefix_hash != expected:
        problems.append(
            Problem(
                WARNING,
                f"the stages this snapshot covers hash to {expected}, but it "
                f"records {snapshot.prefix_hash}: the plan changed at or above "
                "the cut without a minor version bump. Its outputs are being "
                "reused anyway, on the strength of the version alone.",
            )
        )

    if here is not None and snapshot.host is not None:
        theirs, ours = hardware_class(snapshot.host), hardware_class(here)
        if theirs != ours:
            sensitive = _hardware_sensitive_stages(model, snapshot.extent.stages)
            if sensitive:
                problems.append(
                    Problem(
                        ERROR,
                        f"snapshot was produced on {_describe(theirs)}, this is "
                        f"{_describe(ours)}, and stage(s) "
                        f"{', '.join(sensitive)} declare requires_capabilities — "
                        "results from the two are not comparable. Pass "
                        "--allow-mixed-hardware to proceed anyway.",
                    )
                )
            else:
                problems.append(
                    Problem(
                        WARNING,
                        f"snapshot was produced on {_describe(theirs)}, this is "
                        f"{_describe(ours)}. No stage in the snapshot declares "
                        "requires_capabilities, so timings may differ but "
                        "results should not.",
                    )
                )
        if not (snapshot.host or {}).get("host_authoritative", True):
            problems.append(
                Problem(
                    WARNING,
                    "the snapshot's host record describes the machine that "
                    "submitted its run, not the workers that did the work, so "
                    "no comparability verdict is possible for it.",
                )
            )

    return problems
