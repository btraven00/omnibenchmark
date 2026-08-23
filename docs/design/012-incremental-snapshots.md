# 012: Incremental snapshots

[![Status: Draft](https://img.shields.io/badge/Status-Draft-yellow.svg)](https://github.com/omnibenchmark/docs/design)
[![Version: 0.2](https://img.shields.io/badge/Version-0.2-blue.svg)](https://github.com/omnibenchmark/docs/design)

**Authors**: ben
**Date**: 2026-08-23
**Status**: Draft
**Version**: 0.2
**Supersedes**: N/A
**Reviewed-by**: TBD
**Related Issues**: TBD

## Changes

| Version | Date | Description | Author |
|---------|------|-------------|--------|
| 0.1 | 2026-08-22 | Initial draft | ben |
| 0.2 | 2026-08-23 | Rewritten against the implementation; phases 1–3 landed | ben |

## 1. Problem

A benchmark run recomputes everything. In practice the expensive, stable part of
a plan (fetching and preprocessing datasets) is identical across dozens of runs
while only the cheap, volatile part (a new method, a new parameter sweep)
changes. Three cases have no answer today:

- **Sweeps.** Adding one method re-runs every dataset stage.
- **Staged execution.** `scratch/slurm-staged-execution.md` submits phases as
  chained SLURM jobs; each phase must start from what the last one left.
- **Sharing.** "Here are the preprocessed datasets at v1.2" is not expressible.

Design 003 does not cover this: it versions the *whole* output tree, per object,
for publication. What is missing is **slicing** (naming part of a tree) and
**compatibility** (deciding whether a slice may seed another run).

## 2. Goals

- One notion of "part of a run", with set operations on it.
- Reuse that costs no disk (hardlinks) and triggers no recomputation.
- A record of what a run started from, so an incrementally built tree is
  auditable.
- Reuse `RemoteStorage`, `StorageOptions`, the output layout, and Snakemake's
  own DAG resolution. No YAML surface change, so no `api_version` gate.

**Non-goals**: replacing 003 (archival vs. disposable cache); per-file
content-addressed dedup (§7); cross-filesystem materialisation (hardlinks need
one volume, and `EXDEV` is a clear error, never a silent copy); delta
benchmarking itself (§6).

## 3. Concepts

### 3.1 Extent — what a slice covers

Two coordinates: how far down the plan, and which branch of it.

```python
Extent(stages: frozenset[str],          # prefix-closed set of stage ids
       slice_by: str | None = None,     # lineage label the branch cut follows
       slice_values: frozenset[str])    # branches taken; empty = all
```

The branch coordinate is **not** an entrypoint node — a plan may `download` and
`convert` before reaching anything worth calling a dataset, and the interesting
axis may appear at any depth. It is the value of a lineage label, which is what
`provides:` (008 / PR #354) declares. The builtin `dataset` label works today
without that PR.

Nodes **above** the labelling stage carry no value for it. They are the
**trunk**, shared by every branch, and always included:

```
   download   [ ############# trunk ############# ]   label unbound
   dataset    [  iris  |  mnist  |  pbmc  ]           label bound here
   preproc    [  iris  |  mnist  |  pbmc  ]           inherited
   methods    [        |         |        ]           not in extent
```

Both cuts are read straight off the nested output layout (007 §3) — repeated
`<stage>/<module>/.<param_hash>/` triples — so no resolution step is needed.
One axis only: `slice_by` is a single label.

### 3.2 Source — published or local

An output directory produced by `ob run` already carries everything a snapshot
descriptor holds: the plan (`.metadata/benchmark-<sha8>.yaml`), the machine
(`.metadata/manifest.json`), and a layout the extent is read off. So a
colleague's `out/`, or the previous phase of a chained SLURM job, is described
by the same `Snapshot` — built in memory rather than read from disk.

What differs is the guarantee, recorded in a `source` field:

| | `published` | `local` |
|---|---|---|
| Digests | in `MANIFEST` | none |
| Commit point | descriptor written last | none — a live directory |
| Re-fetchable | yes | no |
| Can change under a reader | no (mode 0444) | yes |

`local` is **reusable but not reproducible**, and that matters in exactly one
place: *a pointer to a non-reproducible base is a dangling reference.* An
archive of results derived from a published snapshot names it and omits its
files; one derived from a local tree must inline them (§5.4).

A local base is deliberately not frozen to 0444: `chmod` acts on the shared
inode, so freezing the derived tree would turn someone else's working directory
read-only as a side effect of reading it. The run warns instead.

### 3.3 Compatibility — may this seed that?

`(major, minor)` equality of the declared benchmark version, under the
convention that edits **at or above** the cut bump minor and edits **below** it
bump patch. Adding a branch to the labelling stage is a patch bump too, so a
snapshot covering three datasets stays usable when a fourth is added — the
fourth simply computes from scratch.

That is a promise, not a proof, so the descriptor also records a **prefix
hash**: `Benchmark.summary_hash()` over a copy narrowed to the covered stages,
with metric collectors dropped and software environments restricted to what the
kept modules reference. It delegates to the model's own canonicalisation, so the
two cannot drift. A mismatch is a **warning**, not a refusal: it names the one
failure the version rule structurally cannot catch, while leaving intact the
escape hatch the convention exists for.

### 3.4 Comparability — are the numbers comparable?

Coverage says the cells are filled; it does not say they may be compared. Under
SLURM this is the normal path, not an edge case: staged execution runs each
phase on a different partition by design.

The hardware class is the **SLURM partition and constraint** where available —
a partition is the site's own statement that a set of nodes is interchangeable,
which beats CPU-model strings (too strict on steppings, too loose on clock caps,
silent on accelerators). CPU model and GPU names otherwise.

- Strict where a covered module declares `requires_capabilities` → **error**,
  overridable with `--allow-mixed-hardware`.
- Advisory elsewhere → warning.
- No verdict at all when the source's host record is non-authoritative, i.e.
  produced under a non-local executor where the manifest describes the
  submitting node, not the workers (007 §6).

## 4. Examples

Publishing, against a plan with stages `data → distances → methods → metrics`
and datasets `iris, penguins, D1, D2`:

```bash
ob snapshot push bench.yaml --until data                  # 12 files
ob snapshot push bench.yaml --until distances             # 40 files + 8 links
ob snapshot push bench.yaml --until data --only iris      # one branch
ob snapshot list                                          # ids, extents, counts
ob snapshot verify <id>                                   # full digest check
```

Consuming a snapshot that covers `{data, distances} × all datasets` (48 paths).
A source describes what it *covers*; the flags say what is *taken*:

| command | taken | why |
|---|---|---|
| `ob run b.yaml --from-snapshot <id>` | 48 | all of it |
| `… --after data` | 16 | vertical narrowing |
| `… --filter data:iris` | 19 | horizontal narrowing |
| `… --after data --filter data:iris` | 3 | both compose |
| `… --after methods` | **error** | source stops at `distances` |
| `… --from-snapshot ../prev/out --after data` | 16 | a plain output tree |

`--filter`'s left side is the stage where branches are cut (or the label it
advertises), so the caller never needs to know the label vocabulary. Repeating
it unions branches on one axis; a second axis is an error (§3.1).

Gating, for a snapshot published at version `1.0`:

| plan version | outcome |
|---|---|
| `1.0.7` | reused — patch means edits below the cut |
| `1.1` | **refused**, nothing linked |
| `1.0.8` with a covered module repointed | reused, **warning** naming both prefix hashes |

## 5. How it works

### 5.1 Reuse is materialisation, not DAG surgery

If the outputs are present and not stale, Snakemake does not run their rules.
So starting after a stage needs **no change to Snakefile generation** — the
canonical Snakefile stays whole, matching the decision in
`scratch/slurm-staged-execution.md`. `--until` truncates *resolution* (pruned
modules are never checked out); `--after` touches resolution not at all.

Materialisation is a plain `os.walk` + `os.link`, mtimes preserved. At 50k
files it measures 1.2 s to link, 0.4 s to `chmod`, 3.1 s to `tar` — nothing here
warrants batching or threading. Symlinks (the parameter aliases from
`core/symlinks.py`) are recreated, not linked: `os.link` dereferences them.

### 5.2 Measured against Snakemake 9.6.2

Everything above rests on these, which were tested rather than assumed:

| observation | consequence |
|---|---|
| Generated Snakefiles are fully **relative**; absolutisation happens at shell runtime | a tree is portable between machines with no rewriting |
| `.snakemake/metadata/` records are base64 of relative paths, `code` is the un-substituted template | they too would be portable |
| A **missing** metadata record causes **no** rerun | so they need not be shipped |
| A **present** record with differing `code` **does** rerun | so shipping them could only *add* reruns — they are excluded (§5.3) |
| `output:` files are removed before a job reruns | a hardlinked base is unlinked, never written through |
| `benchmark:` files are written **in place** | they would corrupt a base — so they are never snapshotted |
| A missing `benchmark:` file does not trigger a rerun | excluding them is free |
| Read-only outputs raise `ProtectedOutputException` | mode 0444 is the whole guard, named and loud |
| `tarfile` emits LNKTYPE and `extractall` restores hardlinks | phase 4 preserves them for free |

### 5.3 What a slice excludes, and why

- `.snakemake/`, `.logs/`, `.modules/`, `.metadata/`, `Snakefile` — machinery.
- `performance.txt` / `<dataset>_performance.txt` — Snakemake writes
  `benchmark:` files in place, so a materialised one is written through the
  hardlink into the shared base. They are also per-run *measurements*:
  inheriting them would attribute timings to a run that never produced them,
  which is what §3.4 exists to prevent.

### 5.4 Readiness, integrity, and the run log

Publishing is not atomic, so **the descriptor is the commit point**: payload
first, `MANIFEST` second, `snapshot.json` last and atomically. `list` and
`resolve` key on it, so an interrupted publish leaves a directory that is
invisible rather than half-consumable. Integrity is a chain rooted in that one
atomic write — `snapshot.json` carries the sha256 of `MANIFEST`, which carries
size and sha256 per file.

Hashing rides along with the copy, so it costs no extra read, and the checks
match what each operation can afford:

| operation | check |
|---|---|
| `push` | digest every file (already reading them) |
| `materialize` | presence + size — hardlinks read no bytes |
| `snapshot verify`, remote fetch | full digests |

Verification runs **before anything is linked**, so a bad snapshot never
half-populates a working directory.

`manifest.json` keeps its shape (007 §4.5) and still describes the latest
invocation. The multi-run record is `.metadata/runs.jsonl`, one immutable line
per run — events, not state, so there is nothing to reconcile:

```jsonc
{"run_id": "…", "plan": "639ca73a", "status": "ok",
 "starts_from": ["clustering_benchmark/1.0/03080d1c"], "imported": 16,
 "produced": {"stages": [...], "slice_by": "dataset", "slice_values": []},
 "host": {...}, "slurm": {...}, "host_authoritative": true}
```

It is appended from a `finally`, so a failed or interrupted run is recorded as
such rather than vanishing. `starts_from` holds ids and `imported` is a count:
which files came from a source is already recorded exactly in that source's
`MANIFEST`, so repeating tens of thousands of paths per line would duplicate it
at a cost that grows with the tree.

`save_metadata` also writes `benchmark-<sha8>.yaml` beside `benchmark.yaml`, so
editing a plan between runs no longer destroys the plan that earlier outputs in
the tree were produced under.

**Archiving** subtracts files reused from published sources — read from
`starts_from` and those snapshots' `MANIFEST`s, a lookup and never an inode
heuristic. The run log travels inside the archive, so it *is* the pointer. Files
from a local base are always carried (§3.2), as are files from a source that
cannot be resolved: if we cannot say what it holds, we must not drop files
assuming it does. `--include-base` forces a self-contained archive.

## 6. Delta benchmarking (sketch)

With §3.1, the run log and the two predicates, "delta benchmarking" is a fold
over run entries: start from an extent, apply a run, get a larger extent,
carrying versions, hosts and lineage along. Coverage is
`reduce(or_, produced).covers(plan)`. Nothing here should be generalised in
anticipation of it.

## 7. Alternatives

| Alternative | Why not |
|---|---|
| Per-file content-addressed store (restic-shaped) | The win is deduplication; the problem is recomputation. Coarse payloads + `os.link` solve it with stdlib. Revisit if storage cost, not compute cost, becomes the complaint. |
| Reuse 003 version snapshots | Whole-tree only, per-object transfer, downloads copies (N sweeps = N× disk), and ~19-year Object Lock on something meant to be disposable. Wrong granularity and lifetime. |
| `--after` prunes the DAG | Snakemake already skips fresh outputs. A second Snakefile shape buys nothing and adds drift risk. |
| Branch cut keyed on entrypoint nodes | That is the label scheme with the label hard-coded to "the first stage", and it fails *silently* (one root ⇒ the cut becomes a no-op) rather than loudly. |
| FUSE / overlay / dedup daemon | Root or a daemon per site. Hardlinks are POSIX with one documented constraint. |

## 8. Status

| Phase | State |
|---|---|
| 1 — extent, materialisation, local store, `ob snapshot push/list/verify` | **done** |
| 2 — run log, SLURM and host capture, content-addressed plan copies | **done** |
| 3 — compatibility and comparability gates | **done** |
| 3.5 — `--after`/`--filter` narrowing, local trees as bases, archive subtraction | **done** |
| 4 — S3 store, `tar` payloads, remote fetch | not started |

Phases 1–3 are what the SLURM case needs; it never touches phase 4, because on a
cluster the shared filesystem *is* the remote and `LocalSnapshotStore` addresses
it directly.

## 8.1 Phase 4 — implementation notes

Not started. What is settled, so it need not be re-derived.

### Two caches, not one

The constraint that shapes everything: hardlinks need the output directory's
volume, so the *extracted* payload cannot live in `$HOME` — a home default would
`EXDEV` on exactly the clusters this targets (`/home` vs `/scratch`). Downloaded
tarballs have no such constraint: they are bytes in transit, never a hardlink
source. So they split:

| | holds | default | may be deleted |
|---|---|---|---|
| download cache | `.tar` payloads as fetched | `~/.cache/omnibenchmark/snapshots/` (XDG) | freely — re-fetchable |
| registry | extracted, mode 0444, hardlink source | project-local (today `.ob/cache`) | frees space, forces re-fetch |

Both configurable, following the `get_git_cache_dir()` precedent in
`config.py`: `[dirs] snapshot_downloads` and `[dirs] snapshot_cache`.

Two questions deferred with this and worth settling first: whether a
multi-gigabyte registry should be a **visible, self-ignoring** directory rather
than a dot-directory that hides its size from `ls` and `du`, and an
`ob cache info` / `ob cache clean` command — which only earns its place if it
covers the git module cache too, since `ob snapshot list` already lists
snapshots.

### Payload layout

One archive per branch plus one for the trunk — that is what makes a horizontal
slice cheap to fetch: one dataset costs two objects regardless of how many the
benchmark has. Grouping is `slice_value(lineage(rel), label_stage)` over the
selected paths, with `None` (trunk) going to `_trunk.tar`.

```
<bucket>/
├── config/  software/  out/  versions/     # 003, untouched
└── snapshots/<benchmark_id>/<version>/<extent_key>/
    ├── snapshot.json      # descriptor; written LAST
    ├── MANIFEST           # per-file size + sha256, as locally
    ├── _trunk.tar
    └── <slice_value>.tar
```

`tarfile`, **uncompressed**. Python 3.12/3.13 have no stdlib zstd (3.14 only),
the project has no zstd dependency, and `archive.py` already chose
`ZIP_STORED` for the same reason: benchmark outputs are largely incompressible
and extraction throughput matters more than transfer size. Revisit on a
measurement, not a preference.

Verified behaviours to rely on and not work around: `tarfile` emits `LNKTYPE`
for a second link and `extractall` restores real hardlinks; `filter="data"`
(required from 3.14, and the right default anyway) preserves mtime, which
§5.1 depends on. Extract with `filter="data"`, then `chmod 0444`.

### Commit protocol and integrity

Identical to the local store (§5.4) and for the same reason: payload objects
first, `MANIFEST` second, `snapshot.json` last. A single `PUT` is atomic and S3
has been read-after-write consistent since 2020, so the descriptor's presence is
the readiness signal there too.

One addition the local store does not need: the descriptor must carry a sha256
**per archive**, so a download is checked *before* extraction rather than after.
`MANIFEST` then covers the extracted files as it does locally.

### Layered snapshots

Pushing from a tree that was itself seeded records the source in
`Snapshot.base` and archives only what that source does not already hold.
The subtraction already exists — `snapshot.store.imported_paths()`, written for
the archive layer — and works the same way here: read `starts_from` from the run
log, read those snapshots' `MANIFEST`s, omit what they contain. Fetching a
derived snapshot pulls its bases transitively. Local bases can never be a
`base`, for the dangling-pointer reason in §3.2.

### Guardrails

Decisions that look like oversights and are not: do not ship
`.snakemake/metadata/` in the payload (§5.2 — it can only add reruns); do not
compress by default; do not put the extracted registry under `$HOME`; do not
add per-file content addressing (§7). Named remotes stay unimplemented until
there is a second remote to name — a snapshot elsewhere is a URI.

## 9. References

1. [003-storage.md](./003-storage.md) — remote storage, version snapshots
2. [007-output-layout.md](./007-output-layout.md) — output layout, runtime manifest
3. [008-filtering.md](./008-filtering.md) — `--until`, `provides:` lineage labels
4. `scratch/incremental_manifest.md` — append-only run log
5. `scratch/slurm-staged-execution.md` — staged execution, one canonical Snakefile
6. [Snakemake rerun triggers](https://snakemake.readthedocs.io/en/stable/executing/cli.html#rerun-triggers)
