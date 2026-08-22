# 012: Incremental snapshots — slicing, reuse, and delta benchmarking

[![Status: Draft](https://img.shields.io/badge/Status-Draft-yellow.svg)](https://github.com/omnibenchmark/docs/design)
[![Version: 0.1](https://img.shields.io/badge/Version-0.1-blue.svg)](https://github.com/omnibenchmark/docs/design)

**Authors**: ben
**Date**: 2026-08-22
**Status**: Draft
**Version**: 0.1
**Supersedes**: N/A
**Reviewed-by**: TBD
**Related Issues**: TBD

## Changes

| Version | Date | Description | Author |
|---------|------|-------------|--------|
| 0.1 | 2026-08-22 | Initial draft — extent algebra, snapshot store, hardlink materialisation | ben |

## 1. Problem Statement

A benchmark run recomputes everything. In practice the expensive, stable part of
a plan (fetching and preprocessing datasets) is identical across dozens of runs
while only the cheap, volatile part (a new method, a new parameter sweep) changes.
Three concrete situations today have no answer:

1. **Parameter sweeps.** Adding one method to a plan re-runs every dataset stage.
2. **Staged / SLURM execution.** `scratch/slurm-staged-execution.md` wants to
   submit phases as chained jobs; each phase must be able to start from what the
   previous phase left behind, possibly on a different machine.
3. **Sharing.** A group wants to publish "the preprocessed datasets at v1.2" so
   collaborators can start from there instead of re-deriving them.

Existing storage (003) does not cover this. It versions the *whole* benchmark
output, per object, with S3 Object Lock, addressed by the benchmark version. It
is built for immutability and publication, not for "give me the first three
stages of this plan, for dataset `iris` only, and hardlink them into my working
directory."

Two capabilities are missing:

- **Slicing.** Naming and transferring part of an output tree — a *vertical*
  slice (up to a stage) or a *horizontal* one (a single dataset).
- **Compatibility.** Deciding whether a slice produced by one plan may be reused
  as the starting point of another.

## 2. Design Goals

- **One notion of "part of a run"** that covers both the vertical and the
  horizontal cut, with set operations on it.
- **Cheap reuse**: materialising a fetched slice into a working directory costs
  no disk (hardlinks) and triggers no recomputation.
- **A run can say where it started.** The runtime manifest must record that a run
  began from a snapshot rather than from nothing, so a tree assembled from
  several partial runs can be audited.
- **Reuse what exists**: the `RemoteStorage` port, `StorageOptions`,
  `StorageService`, the `--until` DAG truncation, and Snakemake's own DAG
  resolution.
- **No YAML surface change**, therefore no `api_version` gate. This is a CLI and
  runtime feature only.

### Non-Goals

- Replacing 003 version snapshots. A cache entry is disposable; a 003 version is
  archival. They coexist in the same bucket under different prefixes.
- Content-addressed per-file deduplication (a CAS / restic-style store). Slices
  are coarse-grained tarballs; see §4.
- Cross-filesystem materialisation. Hardlinks require the registry and the
  working directory to be on one volume; this is a documented constraint, not a
  thing to work around with copies.
- Delta benchmarking itself. This document specifies the primitives it needs and
  sketches the shape in §3.9; building it is later work.
- A named-remote registry (`--with-remote FOO` resolving through a config file).
  One benchmark, one configured storage; a snapshot may be named by URI.

## 3. Proposed Solution

### 3.1 Extent — the single concept

A snapshot covers a set of resolved nodes. Rather than enumerate node ids, that
set is described by two coordinates: **how far down** the plan was computed, and
**which branch** of it.

The second coordinate is *not* "which entrypoint node" — a benchmark's datasets
are not necessarily its first stage. A plan may `download` then `convert` then
reach `dataset`, or the axis worth slicing on may be a cohort, a tissue or a
simulation seed introduced halfway down. The coordinate is therefore **the value
of a lineage label**, which is exactly what `provides:` (008 phase 2, PR #354)
declares:

```yaml
stages:
  - id: dataset
    provides: [dataset]          # this stage labels its branch
    modules:
      - id: D1
        provides: {dataset: iris}   # binding is optional; defaults to the module id
```

```python
@dataclass(frozen=True)
class Extent:
    """What a snapshot covers.

    stages:       prefix-closed set of stage ids computed to completion.
    slice_by:     lineage label the horizontal cut is taken on. None = no cut.
    slice_values: values of that label included. Empty = all values.
    """
    stages: frozenset[str]
    slice_by: Optional[str] = None
    slice_values: frozenset[str] = frozenset()

    def covers(self, other: "Extent") -> bool
    def __or__/__and__/__sub__(self, other) -> "Extent"
    def key(self) -> str      # stable sha256[:8] of sorted members
```

#### The trunk

Once the horizontal axis is a label rather than an entrypoint, the covered set
stops being a rectangle. Nodes **upstream of the labelling stage** have no value
for the label — they are shared by every branch:

```
        stages ↓        slice_by = "dataset"

   download   [ ############# trunk ############# ]   label unbound
   convert    [ ############# trunk ############# ]   label unbound
   dataset    [  iris  |  mnist  |  pbmc  ]           label bound here
   preproc    [  iris  |  mnist  |  pbmc  ]           inherited
   methods    [        |         |        ]           (not in extent)
```

An `Extent` therefore covers **the trunk, in full, plus the labelled branches
named in `slice_values`**. Fetching one dataset means fetching the trunk and one
branch. The trunk is not optional and not per-value: it is what every branch is
computed from.

#### Why this needs no new machinery

Partitioning resolved nodes on a label is a lookup on a field that already
exists. `TemplateContext.provides` maps label → value for each node's lineage
(`run.py:_build_template_context`), so:

```python
value = node.template_context.provides.get(extent.slice_by)   # None ⇒ trunk
```

`None` means the node sits above the labelling stage. There is no filesystem
scan, no separate index, and no second definition of "which dataset is this".

The horizontal cut is still a set of path predicates, just not a single one. With
the label bound at the first stage there is one directory prefix per value; with
a trunk above it there is one prefix per (trunk path × value) combination. Those
prefixes are read off the resolved nodes' output paths, so the count is a
property of the plan, not a cost.

#### Constraints worth stating

- **One axis.** `slice_by` is a single label, not a set. Slicing on
  `dataset × cohort` simultaneously is not supported; take the product as one
  label if it is ever needed.
- **Values need not be module ids.** `Module.provides` may bind several modules
  to one value, and the partition is by value. That is the intended behaviour —
  "give me everything labelled `iris`" — but it means a branch is not always a
  single module's subtree.
- **The default is `dataset`.** The runtime already auto-populates the builtin
  `dataset` label (reserved, alongside `name`), so phase 1 works against `main`
  as it stands for the common case where the dataset stage *is* the first stage.
  Declaring `Stage.provides` generalises it; it does not enable it.

### 3.2 Compatibility — the version convention

The question "may this snapshot be the starting point for this plan?" is
answered pragmatically, by the declared benchmark version.

**The convention.** For the cut at which snapshots are taken, the benchmark
author promises:

- a change **at or above** the cut — any stage in `extent.stages`, its modules,
  their pinned commits, parameters, or software environments — bumps **minor**
  (or major);
- a change **strictly below** the cut bumps **patch**.

A change worth calling out explicitly: **adding a module to the labelling
stage is a patch bump**, not a minor one. Adding a fourth dataset changes the
plan above the cut, so the literal rule would invalidate every existing slice —
yet those slices are still byte-valid, and `slice_values` already records that
they do not cover the new one. Treating additive branches as a patch makes
partial coverage do the obvious thing: the three known datasets are fetched, the
fourth computes from scratch.

**The check.**

```python
def is_compatible(snapshot: Snapshot, plan_version: str, want: Extent) -> bool:
    a, b = Version(snapshot.version), Version(plan_version)
    return (a.major, a.minor) == (b.major, b.minor) and snapshot.extent.covers(want)
```

That is the whole compatibility layer. It buys a large amount of avoided
complexity: no per-node fingerprinting, no environment solving, no comparison of
resolved DAGs.

**What it costs, stated plainly.**

- *It is unverified.* An author who edits a dataset module and bumps patch gets
  silent, wrong reuse. There is no way for ob to catch this under this rule.
- *It supports exactly one cut per benchmark.* `(major, minor)` is a single
  boolean boundary, so a benchmark cannot promise stability at both "up to
  datasets" and "up to preprocessing" independently.

**The upgrade path**, when either cost bites: replace the version comparison with
a **prefix hash** — `Benchmark.summary_hash()` (003 phase 1, 004 §9) computed
over the truncated stage list rather than the whole plan. It is a few lines on
top of a method that already exists, it is per-cut so it removes the one-cut
limit, and it is verifiable rather than promised. Snapshots therefore record the
prefix hash from day one (§3.3) even though phase 1 does not *gate* on it.

Phase 4 adds one cheap intermediate step rather than jumping straight to a hash
gate: **gate on the version, warn on a prefix-hash mismatch.** Three lines, no
new flag, no discipline required of the author, and it converts the one failure
mode the convention cannot catch — a plan edited above the cut without a minor
bump — from silent reuse into a visible message. The escape hatch the convention
exists for (an author asserting that a cosmetic change above the cut is
irrelevant) survives, because the mismatch is a warning and not a refusal. §3.5
makes this worth doing: Snakemake will not catch the mismatch either.

Should the warning prove to be the common case rather than the rare one, promote
it to the gate; a per-branch prefix hash (trunk + that branch's modules) then also
recovers partial reuse when a dataset is added, which is the one case the
convention currently handles better.

### 3.3 Snapshot descriptor and archive layout

```python
@dataclass(frozen=True)
class Snapshot:
    id: str                      # "<benchmark_id>/<version>/<extent_key>"
    benchmark_id: str
    version: str                 # benchmark version that produced it
    prefix_hash: str             # summary_hash() over extent.stages (recorded, unused in phase 1)
    extent: Extent
    archives: Dict[str, str]     # slice value (or "_trunk") -> object key
    manifest_sha256: str         # roots the integrity chain (§3.3.1)
    base: List[str]              # snapshot ids this one was layered on (§3.6)
    ob_version: str
    host: Dict                   # the manifest host block, for §3.8
```

**One archive per slice value, plus one for the trunk** — not one per snapshot.
That is what makes the horizontal slice usable: fetching dataset `iris` alone
means fetching two objects (`_trunk.tar` + `iris.tar`) regardless of how many
other datasets the benchmark has. Archives hold benchmark outputs only — not
`.snakemake/` state, for the reason measured in §3.5. When `slice_by` is None the
whole extent is one `_trunk.tar`.

Bucket layout, alongside the 003 prefixes:

```
<bucket>/
├── config/ software/ out/ versions/     # 003, unchanged
└── snapshots/
    └── <benchmark_id>/<version>/<extent_key>/
        ├── snapshot.json                # the descriptor above; written LAST
        ├── _trunk.tar                   # nodes above the labelling stage
        └── <slice_value>.tar            # one archive per labelled branch
```

Local registry, shared across working directories:

```
.ob/cache/<benchmark_id>/<version>/<extent_key>/<_trunk|slice_value>/…  # extracted, immutable
```

**Compression: none.** Python 3.12/3.13 have no stdlib zstd (3.14 only) and the
project has no zstd dependency; `archive.py` already defaults to
`zipfile.ZIP_STORED` for the same reason — benchmark outputs are largely
incompressible and extraction throughput matters more than transfer size. Plain
`tarfile`, no new dependency. Revisit with a measurement, not a preference.

### 3.3.1 Readiness and integrity

Publishing a snapshot is not atomic — it writes many files, or uploads many
objects, over a period in which a consumer may look. Without a commit point a
half-written snapshot is indistinguishable from a complete one, and a consumer
can hardlink a truncated file into a working directory and compute on it. The
failure is silent, and it propagates: the bad bytes become inputs to everything
downstream.

**The descriptor is the commit point.** Payload first, `MANIFEST` second,
`snapshot.json` last and atomically (`os.replace` locally; a single `PUT` is
atomic on S3, which has been read-after-write consistent since 2020). Both
`list` and `resolve` key on the descriptor's presence, so an interrupted publish
leaves a directory that is *invisible* rather than half-consumable. Rewriting an
existing snapshot removes the descriptor first, for the same reason. A second
publish of the same id is refused unless `--force`: identical content makes
last-writer-wins harmless, but a partial overwrite would not be.

**Integrity is a chain rooted in that one atomic write.** `snapshot.json` carries
the sha256 of `MANIFEST`; `MANIFEST` carries the size and sha256 of every file:

```
snapshot.json ──sha256──▶ MANIFEST ──size+sha256──▶ every payload file
   (atomic)
```

So everything a consumer received can be checked against a single record that
either landed whole or not at all. Tampering with `MANIFEST` to match doctored
payload fails against the descriptor.

**Hashing is free where the bytes are already moving, and skipped where they are
not.** Publishing copies, so the digest is computed *during* the copy — one pass,
no extra read. The checks then match what each operation can afford:

| Operation | Check | Why |
|---|---|---|
| `push` | digest every file while copying | already reading the bytes |
| `materialize` | presence + size (stat only) | hardlinks read no bytes; a full pass would be the slowest step of an otherwise instant operation |
| `materialize --verify` | full digests | opt in when it matters |
| `snapshot verify` | full digests | that is the command's whole job |
| remote fetch (§3.3) | full digests, always | the download already reads every byte |

The default is not a compromise: size-and-presence is exactly what catches the
failure this section exists for — a truncated or missing payload from an
interrupted write. Same-size corruption is a different threat (bit rot, a
tampering editor) and needs the deep pass, which is why `verify` exists.

**Verification happens before anything is linked**, so a bad snapshot can never
half-populate a working directory and leave the user to work out which files are
real.

### 3.4 The port

`omnibenchmark/storage/base.py` already defines the storage port
(`RemoteStorage`) and `omnibenchmark/remote/` its S3 implementation. **No second
storage abstraction is introduced.** A snapshot store is a thin thing layered on
top:

```python
class SnapshotStore(Protocol):
    def list(self, benchmark_id: str) -> List[Snapshot]: ...
    def fetch(self, snap: Snapshot, values: Iterable[str], registry: Path) -> Path: ...
    def push(self, snap: Snapshot, out_dir: Path, values: Iterable[str]) -> None: ...
```

Two implementations justify the protocol:

- `S3SnapshotStore` — wraps an existing `RemoteStorage` obtained from
  `StorageService`; inherits its credential handling and endpoint config.
- `LocalSnapshotStore` — a directory. Used by tests (no container needed) and by
  HPC sites where a shared filesystem *is* the remote.

New module: `omnibenchmark/snapshot/` (`extent.py`, `store.py`, `link.py`),
depending on `storage` and `core`, and depended on by `cli`. It does not import
`remote` directly — `StorageService` stays the seam, as it is for `archive`.

### 3.5 Materialisation — and why `--after` is not a DAG operation

Fetch extracts into the registry once; materialisation hardlink-mirrors the
registry into `out/`. `os.link` per file, directories created normally, mtimes
preserved (`tarfile.extractall` already does this). Zero additional disk.

The important consequence:

> **Starting a run "after" a stage requires no changes to DAG generation.**
> If the outputs of the earlier stages are present and not stale, Snakemake does
> not run their rules. `--after` is a *materialisation* operation, not a pruning
> operation.

The resolved Snakefile therefore stays the canonical, complete one — the decision
already taken in `scratch/slurm-staged-execution.md` — and `--until` / `--after`
are deliberately asymmetric: `--until` truncates *resolution*, so pruned modules
are never checked out; `--after` touches resolution not at all.

#### Verified against Snakemake 9.6.2

Four properties this rests on were measured, not assumed:

1. **The generated Snakefile is position-independent.** Every `input:`,
   `output:`, `log:` and `params.module_dir` in a generated Snakefile is
   *relative* to the output directory (`data/D1/.default/D1.txt.gz`,
   `.modules/process/3b17081`); absolutisation happens at shell runtime via
   `$(cd … && pwd)`. A tree produced on one machine is therefore describable
   identically on another.
2. **Snakemake's own per-output records are relocatable too.**
   `.snakemake/metadata/<base64 of the relative output path>`, and the stored
   `code` is the *un-substituted* rule template. Nothing machine-specific.
3. **A missing record does not cause a rerun.** With outputs present and
   `.snakemake/` absent entirely, upstream jobs are skipped and only the
   downstream job is scheduled.
4. **A present record with differing `code` does cause a rerun.**

Properties 3 and 4 together settle a question the first draft got wrong.

#### The `.snakemake/metadata/` records are *not* shipped

The first draft proposed including them in each archive so the materialised tree
would be indistinguishable from a locally computed one. Given (3) and (4) that is
backwards: shipping the records can only ever *add* reruns, never prevent one. A
single cosmetic difference between producer and consumer plan — the kind
`is_compatible` is designed to tolerate — would re-run the entire fetched slice
and defeat the feature. Not shipping them is both less code and strictly safer.

The trade, stated plainly: **Snakemake will not second-guess a plan mismatch.**
`is_compatible` (§3.2) is the only gate. That is the intended bargain of the
version convention, not an oversight — but it does mean a wrong version bump
produces silently reused outputs rather than a rerun. `ob snapshot verify` may
later restore the records into a scratch directory and run `snakemake -n` as an
opt-in strict check; that is a diagnostic, not the mechanism.

#### The registry is protected by mode, and Snakemake already handles it

Hardlinks are not copy-on-write. The claim that "subsequent outputs generate
entirely new inodes" is **not true in general**: a module that opens an output
in place (`>` redirect, truncate, append) writes *through* the link into the
shared registry and corrupts it for every other working directory.

The guard is one `chmod 0o444` at extraction time, and Snakemake implements the
rest:

```
ProtectedOutputException in rule a:
Write-protected output files for rule a:
    affected files:
        a.txt
```

Measured behaviour with a read-only registry: an in-place truncate through the
link fails with `EACCES`; downstream rules read the file normally; and a rule
that would recompute a materialised output aborts with the named exception above
instead of silently clobbering shared cache. Recomputing on purpose therefore
requires explicitly dropping the link (`ob snapshot unlink`, or a
`--force-recompute` that unlinks first) — a loud, explicit path rather than a
quiet one.

One materialiser detail that is a bug if missed: the output tree contains
symlinks — the human-readable parameter aliases from `core/symlinks.py`
(`measure-chebyshev → .7303dd4b`) — and `os.link` **dereferences** them. Symlinks
must be recreated with `os.symlink(os.readlink(src), dst)`, not linked. Their
targets are relative and stay inside the slice, so they survive relocation.

Two limits worth recording. `chmod` acts on the inode, so registry files and
their links in `out/` share one mode; anything that relaxes the mode in the
working directory un-protects the registry. And the constraint that gives all of
this its cheapness stands: registry and working directory must be on one volume,
`EXDEV` is a clear error and never a silent copy.

### 3.6 Manifest extension — a run that starts from a snapshot

`scratch/incremental_manifest.md` already recommends an append-only
`.metadata/runs.jsonl` alongside `manifest.json` (which keeps its shape and
meaning: the latest invocation). This design needs that log, plus two fields:

```jsonc
// .metadata/runs.jsonl, one line per `ob run`
{
  "run_id": "550e8400-…",
  "timestamp": "2026-08-22T14:30:00Z",
  "ob_version": "0.7.0",
  "plan": "sha8-of-benchmark-yaml",          // per incremental_manifest.md §B
  "starts_from": ["iris-bench/1.2.0/a1b2c3d4"],   // snapshot ids materialised in
  "imported": ["data/iris/…", …],            // paths hardlinked, not computed
  "produced": {"stages": ["methods"], "slice_by": "dataset", "slice_values": ["iris"]},
  "host": { … },                             // as manifest.json
  "slurm": {"cluster": "…", "partition": "gpu", "constraint": "a100", …},
  "host_authoritative": true                 // false under `--executor slurm`
}
```

`imported` is written by the materialiser, which knows exactly which paths it
linked. **Do not infer imported files from `st_nlink > 1`** — inode forensics is
guesswork where a record is free; `st_dev`/`st_ino` comparison against the
registry is worth having only as an assertion in `ob snapshot verify`.

`imported` is what makes layered snapshots work: pushing a snapshot from a tree
that started from another one archives `produced` only and records the parent in
`Snapshot.base`. Fetching a derived snapshot pulls its bases transitively. This
is the "only snapshot the non-hardlinks and leave pointers" behaviour, with the
pointer being an explicit list rather than a filesystem heuristic.

This log is the thing that gets threaded through a chain of partial runs: each
run reads the extents it started from and appends the extent it produced. That is
the execution context §3.9 consumes.

### 3.7 Coverage — when do several chunks equal a whole plan?

```python
def covered(runs: Iterable[RunEntry], plan: Extent) -> bool:
    return reduce(or_, (r.produced for r in runs), Extent(frozenset())).covers(plan)
```

Set arithmetic on §3.1, nothing more. A tree assembled from a fetch plus three
partial runs is complete iff the union of extents covers the full plan's extent.

### 3.8 Equivalence — when are the chunks *comparable*?

Coverage says the cells are filled; it does not say the numbers may be compared.
This is not a hypothetical multi-site concern — **it is the normal path under
SLURM.** The staged model in `scratch/slurm-staged-execution.md` deliberately
runs each phase on a different partition (fetch on `cpu`, methods on `gpu`), so a
single assembled tree is *by construction* the product of several hardware
classes. Comparability has to be established, not assumed.

#### Borrow the site's hardware classes; do not invent one

Matching on `cpu_model` strings is a bad equivalence relation: it is too strict
(a stepping difference is not a comparability difference), too loose (same model,
different memory bandwidth or clock cap), and it has no answer for accelerators.

A cluster already publishes an authoritative partition of its hardware — the
**partition**, plus any **constraint/feature** selectors. That is the site
saying, in its own words, "these nodes are interchangeable." So:

```python
def hardware_class(run: RunEntry) -> tuple:
    if run.slurm:                       # authoritative
        return ("slurm", run.slurm["cluster"], run.slurm["partition"],
                run.slurm.get("constraint"))
    return ("host", run.host["cpu_model"],                      # best effort
            tuple(g["name"] for g in run.host.get("gpu_devices") or ()))
```

Capturing it is ~10 lines in `backend/_manifest.py`: when `SLURM_JOB_ID` is set,
record `SLURM_CLUSTER_NAME`, `SLURM_JOB_PARTITION`, `SLURM_JOB_CONSTRAINT`,
`SLURM_JOB_NODELIST`, `SLURM_JOB_CPUS_PER_NODE` and `SLURM_JOB_GPUS`. No new
dependency, no `scontrol` call, no taxonomy to maintain.

#### The verdict is per-stage, and strict only where declared

- **Method stages** — timings are comparable only within one hardware class.
- **Stages with a module declaring `requires_capabilities`** — strict. The
  declared capabilities must match, and where `gpu` is among them the device
  model must too. Mismatch is an **error**, overridable with
  `--allow-mixed-hardware`. This reuses the capability gating already on `main`
  (`bac29c6`), which is precisely the existing marker for "this module is
  hardware-sensitive."
- **Dataset and metric stages** — hardware-insensitive in practice. Mismatch is a
  note in the run log.

#### Where this lands, and the one topology it cannot serve

The right granularity is the **run**, not the benchmark: each phase of a chained
SLURM submission is its own `ob run` on its own allocation, so its `runs.jsonl`
entry records the hardware that phase actually used. The append-only log (§3.6)
therefore resolves, for this topology, the worker-attribution gap 007 §6 records
as an accepted loss — not by adding machinery, but because the unit of execution
and the unit of provenance finally coincide.

That holds for **topology B** (job-per-phase, `--dependency=afterok`), which
`slurm-staged-execution.md` already prefers for long and GPU-bound runs. It does
**not** hold for **topology A** (`--executor slurm`, one controller submitting
per-rule jobs): there the manifest describes the submitting node — typically a
login node with no GPUs — while the work happens on workers whose hardware is
never recorded. `gpu_devices: null` from a login node is wrong *and* silent.

Detecting this is one string check on the recorded `snakemake_cmd`. When
`--executor slurm` is present, mark the run entry `host_authoritative: false` and
refuse to issue a comparability verdict for it, with a message saying why.
Per-worker capture (007 §6.1's `.metadata/workers/worker-<host>.json`) is the fix
if topology A is ever needed; the honest warning is what ships.

### 3.9 Delta benchmarking (sketch, not in scope)

With §3.1, §3.6, §3.7 and §3.8 in place, "delta benchmarking" is a fold over run
entries: start from an extent, apply a run, get a larger extent, carrying the
context (versions, hosts, snapshot lineage) along. The primitives it needs are
exactly the four above — extent algebra, an appendable context, a coverage
predicate and an equivalence predicate. Nothing in this document should be
generalised in anticipation of it; if the fold is ever written it will be a
module that consumes these, not a change to them.

### 3.10 CLI surface

```bash
# produce
ob run bench.yaml --until data              # existing (008 phase 1)
ob snapshot push bench.yaml --until data    # archive + upload the vertical slice
ob snapshot push bench.yaml --until data --slice-by dataset   # default: dataset
ob snapshot push bench.yaml --until data --only iris          # one branch only

# consume
ob snapshot list bench.yaml
ob run bench.yaml --from-snapshot <id|uri>          # fetch, link, run the rest
ob run bench.yaml --from-snapshot <id> --only iris  # horizontal narrowing
ob run bench.yaml --from-snapshot <id> --after data # optional assertion (see below)

# inspect
ob snapshot verify bench.yaml     # registry links intact, digests match, extents cover
```

Two notes on the flags:

- **`--from-snapshot` carries the cut; `--after STAGE` does not need to.** The
  snapshot's own extent already says where it stops. `--after` is therefore
  accepted as an *assertion* — "I expect the fetched slice to end at `data`" —
  and errors if the extent disagrees. It is not the mechanism. Making the stage
  name the mechanism would duplicate, in the CLI, a fact the descriptor already
  carries, and would let the two disagree.
- **`--only` names a value, not `label=value`.** The descriptor already records
  `slice_by`, so repeating the label in the consumer's flag would let the two
  disagree — the same argument as `--after`. `--slice-by` appears only on
  `push`, where the label is genuinely being chosen.
- **`--with-remote FOO` is not implemented.** The benchmark's configured storage
  is the default remote; a snapshot elsewhere is named by URI in
  `--from-snapshot`. A named-remote registry is a config feature to add when
  there is a second remote to name.

## 4. Alternatives Considered

### Alternative 1: content-addressed store (per-file CAS)
- **Description**: hash every output file, store by digest, reconstruct trees
  from a file list. Restic / git-annex shape.
- **Pros**: perfect deduplication across versions; slicing is free; compatibility
  is exact rather than promised.
- **Cons**: an index to maintain and garbage-collect; many small objects instead
  of a few large ones (S3 request cost and latency); every path in the design
  above gets a lookup layer.
- **Reason for rejection**: the win is deduplication, and the actual problem is
  *recomputation*. Coarse tarballs plus hardlinks solve the stated problem with
  stdlib `tarfile` and `os.link`. Revisit if storage cost, not compute cost,
  becomes the complaint.

### Alternative 2: reuse 003 version snapshots directly
- **Description**: `ob remote files download -v 1.2` into `out/`, then run.
- **Pros**: already implemented; exact object versions.
- **Cons**: whole-tree only — no vertical or horizontal slice; per-object
  transfer; downloads copies rather than linking, so N sweeps cost N× disk;
  Object Lock retention (≈19 years) on entries that are meant to be disposable.
- **Reason for rejection**: wrong granularity and wrong lifetime. 003 stays the
  archival mechanism; this is the cache. Same bucket, different prefix.

### Alternative 3: `--after STAGE` prunes the DAG
- **Description**: generate a Snakefile containing only the stages after the cut,
  treating fetched files as given inputs.
- **Pros**: superficially symmetric with `--until`.
- **Cons**: a second Snakefile shape to keep consistent with the canonical one;
  node ids and paths must be shown to agree between the two; loses resume and
  loses the full DAG in `--dry`.
- **Reason for rejection**: Snakemake already skips rules whose outputs are
  present and fresh. The pruning buys nothing and costs a drift risk — the same
  argument already recorded in `scratch/slurm-staged-execution.md`.

### Alternative 4: key the horizontal slice on entrypoint nodes
- **Description**: partition by root node id, so a slice is one entrypoint's
  descendant subtree — one directory prefix, no trunk, no label lookup.
- **Pros**: simplest possible partition; works with no dependency on `provides:`.
- **Cons**: assumes the dataset stage is the first stage. It is not, in general —
  a plan may fetch and convert before it reaches anything worth calling a
  dataset, and the axis worth slicing on may be introduced at any depth. Under
  this scheme such a plan has exactly one root, so the horizontal cut silently
  becomes a no-op rather than an error.
- **Reason for rejection**: it is the label scheme with the label hard-coded to
  "the first stage", and it fails silently rather than loudly when that is wrong.
  §3.1 keeps the property that made it attractive — the cut is still a set of
  path prefixes read off resolved nodes — at the cost of a trunk archive.

### Alternative 5: FUSE / overlay mount or a dedup daemon
- **Reason for rejection**: root or a daemon in the execution path, per site.
  Hardlinks are POSIX, need no privileges, and have one documented constraint
  (same volume).

## 5. Implementation Plan

Phases are independently useful; each lands on a main containing the previous.
Phase 1 depends on `--until` (008 phase 1) being merged.

**Phase 1 — extent + local materialisation.** *(implemented)*
`snapshot/extent.py` (`Extent`, `covers`, `|`, `key()`, and `lineage()` decoding
the output layout), `snapshot/link.py` (selection, hardlink mirror, symlink
recreation, mode 0o444, digest-while-copying), `snapshot/plan.py` (stage closure,
label binding), `snapshot/store.py` (descriptor, `MANIFEST`, commit protocol,
`verify`, `materialize`, `LocalSnapshotStore`). CLI: `ob snapshot
push/list/verify` and `ob run --from-snapshot`. No S3, so it is testable with no
network and no container.

**Phase 2 — run log and host capture.** `.metadata/runs.jsonl` with
`starts_from` / `imported` / `produced`, the content-addressed
`benchmark-<sha8>.yaml` copy (`scratch/incremental_manifest.md` A + B), the
`SLURM_*` block and the `host_authoritative` flag (§3.8). `manifest.json` keeps
its shape, so 007 §4.5's stability guarantee holds. Enables layered snapshots
(`Snapshot.base`).

**Phase 3 — compatibility and equivalence gates.** `is_compatible` on
`(major, minor)` with the prefix-hash warning (§3.2); `hardware_class()` and the
per-stage verdict; `--allow-mixed-hardware`; `ob snapshot verify`.

**Phase 4 — descriptor, archives, S3.** `Snapshot`, `tarfile` per-branch
archives, `S3SnapshotStore` over `StorageService`, `snapshots/` prefix, digest
verification on fetch. CLI gains `--only` and URI-addressed `--from-snapshot`.

The order is driven by the SLURM case, which is the nearest concrete consumer:
**it needs phases 1–3 and never touches phase 4**, because on a cluster the
shared filesystem *is* the remote and `LocalSnapshotStore` addresses it directly.
S3 matters for sharing slices between sites, which is a later problem. Label
partitioning throughout uses the builtin `dataset` label; declared
`Stage.provides` (PR #354) widens it with no code change here.

Cost is dominated by nothing: at 50k output files — the working scale — the
materialiser measures 1.2 s to hardlink, 0.4 s to `chmod`, and 3.1 s to `tar`.
No batching, threading or progress reporting is warranted; keep it a plain walk.

Deferred, with a `ponytail:` marker at each site: prefix-hash *gating* (the
warning ships in phase 3), per-worker host capture for SLURM topology A,
compression, named remotes, per-file run attribution, delta-benchmarking fold.

### Testing Strategy

- **Unit**: `Extent` set algebra and `covers()`, including
  empty-slice_values-means-all and mismatched `slice_by` never covering;
  `key()` stability under member reordering; `is_compatible` across
  major/minor/patch differences.
- **Unit**: hardlink materialiser — link count 2 after mirroring, identical
  `st_ino`, mtimes preserved, mode 0o444 applied, `imported` list matches what
  was linked, and a clear error (not a copy fallback) on `EXDEV`.
- **Integration, the check that matters**: run a fixture to completion, push a
  snapshot at `--until data`, wipe `out/`, `ob run --from-snapshot` into the
  clean directory, and assert that **the data-stage rules execute zero jobs**
  while the downstream stages run. Assert the registry files' link count *grew*,
  i.e. no copy. This is the one test that fails if any assumption in §3.5 stops
  holding on a future Snakemake.
- **Integration, the guard**: force a rerun of a materialised rule and assert
  `ProtectedOutputException` plus a byte-identical registry — the regression test
  for cache corruption.
- **Integration**: horizontal slice — push with two branches, fetch one, assert
  only that branch is materialised and the other is computed from scratch.
- **Integration, the trunk**: a fixture whose labelling stage is *not* first
  (`download → dataset → preproc`). Fetching one branch must materialise the full
  trunk plus that branch, and the trunk's rules must execute zero jobs. This is
  the test that fails if the horizontal cut is ever re-keyed on entrypoints.
- **Integration**: layered push — run from a snapshot, push again, assert the
  second archive contains only `produced` paths and names the first in `base`.
- **Unit**: `hardware_class()` — SLURM env present wins over host fields; a
  differing partition is a different class; `--executor slurm` in `snakemake_cmd`
  sets `host_authoritative: false` and suppresses the verdict.
- **Integration, readiness**: delete a published descriptor and assert the
  snapshot becomes invisible to `list`/`resolve` rather than partly usable;
  truncate a payload file and assert the shallow check rejects it; corrupt a file
  to the same size and assert only the deep check catches it; doctor `MANIFEST`
  and assert the descriptor's digest catches that.
- **e2e (S3)**: extend the RustFS container suite (`tests/e2e/test_06_s3_remote.py`)
  with a push/fetch round trip and digest mismatch handling.

## 6. Relationship to Existing Documents

| Doc | Relationship |
|-----|--------------|
| 003 storage | Complementary. 003 = archival, per-object, Object Lock, whole-tree, keyed by version. This = disposable cache, sub-tree tarballs, keyed by (version, extent). Shares the `RemoteStorage` port, credentials and bucket; distinct `snapshots/` prefix. |
| 007 output layout | Extends `.metadata/` with `runs.jsonl`; leaves `manifest.json` unchanged. Relies on the nested layout (§3) making the horizontal slice a path prefix. |
| 008 filtering | `--until` supplies the vertical cut: `Extent.stages` is the set `_apply_until_filter` already computes. Its lineage half (`Stage.provides` / `Module.provides`, PR #354, api ≥ 0.6.0) supplies the horizontal one: `Extent.slice_by` is a declared label, and `TemplateContext.provides` maps each node to its value. Phase 1 rides the builtin `dataset` label and needs neither PR merged; anything beyond "the dataset stage is the first stage" needs #354. |
| `scratch/incremental_manifest.md` | Phase 3 is that note's recommendations A and B, with `starts_from` / `imported` / `produced` added. Its finding 2 (never stamp a run id into rule text) is a hard constraint here — it would invalidate every job and destroy the reuse this design exists to provide. |
| `scratch/slurm-staged-execution.md` | The nearest concrete consumer, and the reason §3.8 exists rather than being deferred: its chained-phase model runs each phase on a different partition by design. Topology B makes each phase its own `ob run`, so the run log captures the hardware that phase used — closing, for that topology, the worker-attribution gap 007 §6 records as accepted loss. Needs phases 1–3 only. |

## 7. References

1. [003-storage.md](./003-storage.md) — remote storage and version snapshots
2. [007-output-layout.md](./007-output-layout.md) — output layout and runtime manifest
3. [008-filtering.md](./008-filtering.md) — `--until` and DAG truncation
4. `scratch/incremental_manifest.md` — append-only run log, plan content-addressing
5. `scratch/slurm-staged-execution.md` — staged execution, one canonical Snakefile
6. [Snakemake rerun triggers](https://snakemake.readthedocs.io/en/stable/executing/cli.html#rerun-triggers)
