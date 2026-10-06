# RAT — Repo Analysis Tool · Project Structure & Context Map

> **Purpose:** Living context document. Single source of truth for requirements, architecture,
> codebase structure, decisions, and status — updated continuously as the project evolves, so
> we never need to re-read the full brief or re-scan the codebase each session.
>
> **Source brief:** `COMS3011A Test - test_brief.md` (converted from `COMS3011A Test - test_brief.pdf`).
> All formulas below were verified against the original PDF on 2026-10-06 (the md conversion had
> garbled the math). Notation matches the brief exactly: lowercase `h` = a commit, `H` = a commit set.
>
> **Last updated:** 2026-10-06 — Phase: pre-build. Brief fully captured (§1–§3, all formulas).
> Awaiting go-ahead for the metrics deep-dive before building anything.

---

## 1. What We're Building

**RAT (Repo Analysis Tool)** — a web-app dashboard that computes code metrics over git repositories,
for **each author, each file, each directory, and the repository as a whole**.

Motivation: git repos are opaque — RAT surfaces how a repo evolved, who impacted what, and which
parts are most volatile.

**Acceptance inputs (two forms):**
1. A **zip file** of the repo containing the `.git` directory
2. A **remote repository URL**, deeply cloned (full history required for metrics)

**Test constraints:** 2.5 hour timebox · submission = URL to a public repository.

---

## 2. Feature List (from brief §1)

| # | Feature | Detail |
|---|---------|--------|
| F1 | Zip ingestion | Upload of a repo zip containing `.git` |
| F2 | URL ingestion | Remote URL → deep clone (all history, all refs as needed) |
| F3 | Multi-repo support | Dashboard can hold/switch between multiple repositories |
| F4 | Author merging | Via git `.mailmap`; **and** manual author merge when no mailmap exists |
| F5 | Metric categories | File · Directory · Repository · Commit Set · Author |

**Dashboard filtering (part of "Filtering" in rubric):**
- By repository
- By author
- By file or directory
- By commits
- By a specified period of time
- By a manually selected list of commits

> Brief's note: *not all features are strictly necessary* — the rubric tiers define what is needed.

---

## 3. Domain Model (brief §2 — key definitions)

### Commits & commit sets (brief notation: `h` = a commit, `H` = a commit set)
- A commit `h` has: exactly **one author `h[a]`** (after author merging), a **previous commit
  `h[p]`** (the initial commit's `h[p] = h_∅`, a virtual *empty commit* — so the first real
  commit diffs against an empty tree), and a **committer date `h[committer-date]`**.
- **Merge commits are excluded** from analysis: `H̄` = set of non-merge commits reachable from a
  reference commit `h_r` (typically HEAD). A **commit set** `H` is any subset of `H̄`.
- Time-based commit sets:
  - `H_t := {h ∈ H̄ | t ≤ h[committer-date]}` — from UNIX timestamp `t` → present
  - `H_{i,j} := {h ∈ H̄ | i ≤ h[committer-date] < j}` — `i` inclusive → `j` **exclusive**

### Objects (files & directories)
- `h[F]` = all files at commit `h`; `h[D]` = all directories. For a commit set:
  - `H[F] := ⋃_{h∈H} (h[F] ∪ h[p][F])` — union over commits **and their previous commits**
    (this is what captures deleted objects as still-measurable paths)
  - `H[D] := ⋃_{h∈H} (h[D] ∪ h[p][D])` — all directories **including the root**
- An object is identified **by its path**.
- **Binary files are not measured** — use git's own definition/detection.
- **Rename detection at 50% similarity threshold** (like git `-M50%`):
  - A pure rename must **not** change the object's metrics.
  - Rename **plus** changes: only the changes impact metrics, attributed to the **new path**.
- **Deletion** (object exists in `h[p]` but not in `h`) → recorded as a change (lines removed)
  on its path.

### Directory membership ("immediate objects")
- An *immediate object* of directory `d` is directly below it (e.g. `foo/bar.txt` is an immediate
  child of `foo/`; `baz/beef.py` is not — it belongs to `baz/`).
- A file `f` is in directory `d` at commit `h` if it is an immediate child of `d` in `h[F]` **or**
  `h[p][F]` (same for subdirectories with `h[D]` / `h[p][D]`). This ensures adds, deletes,
  and moves across the diff are all attributed to the containing directory.

---

## 4. Metrics (formulas verified against the PDF, 2026-10-06)

> Brief notation: `h` = commit · `H` = commit set · `o` = object (file or directory) ·
> `a` = author · `l⁺`/`l⁻` = added/removed lines · `δ` = growth · `λ` = churn ·
> `n` = modifications · `η` = modification frequency · `ρ` = churn rate · `ω` = ownership.

### 4.1 File metrics (per commit `h`, vs `h[p]`) — brief §2.1
| Metric | Formula |
|--------|---------|
| File Added Lines | `l⁺_{h,f}` — lines added on file `f` from `h` to `h[p]` |
| File Removed Lines | `l⁻_{h,f}` — lines removed on file `f` from `h` to `h[p]` |
| File Growth | `δ_{h,f} := l⁺_{h,f} − l⁻_{h,f}` |
| File Churn | `λ_{h,f} := l⁺_{h,f} + l⁻_{h,f}` |

### 4.2 Directory metrics (per directory `d`) — brief §2.2
Recursive aggregation over **immediate** children (files `f ∈ d`, subdirectories `d' ∈ d`):
- Added: `l⁺_{h,d} := Σ_{f∈d} l⁺_{h,f} + Σ_{d'∈d} l⁺_{h,d'}` (Removed: same form with `l⁻`)
- Growth: `δ_{h,d} := Σ_{f∈d} δ_{h,f} + Σ_{d'∈d} δ_{h,d'}`
- Churn: `λ_{h,d} := Σ_{f∈d} λ_{h,f} + Σ_{d'∈d} λ_{h,d'}`

→ Each directory = its immediate files + its immediate subdirectories (which recurse), so values
roll up the whole tree. **Repository metrics = directory metrics at the root (brief §2.3).**

### 4.3 Commit set metrics (on object `o ∈ H[F] ∪ H[D]`) — brief §2.4
- Added / Removed / Growth / Churn over the set:
  `l⁺_{H,o} := Σ_{h∈H} l⁺_{h,o}` · `l⁻_{H,o} := Σ_{h∈H} l⁻_{h,o}` ·
  `δ_{H,o} := Σ_{h∈H} δ_{h,o}` · `λ_{H,o} := Σ_{h∈H} λ_{h,o}`
- Modification indicator: `𝕀ⁿ(h,o) := 1` if `λ_{h,o} > 0`, else `0`
- **Modifications** — `n_{H,o} := Σ_{h∈H} 𝕀ⁿ(h,o)` — # commits with at least some change on `o`
- **Modification Frequency** — `η_{H,o} := n_{H,o} / |H|` if `|H| ≠ 0`, else `0`
- **Churn Rate** — `ρ_{H,o} := λ_{H,o} / |H|` if `|H| ≠ 0`, else `0`

### 4.4 Author metrics (on `o ∈ H[F] ∪ H[D]`, author `a`) — brief §2.5
- Authorship test: `𝕀(a,h) := 1` if `a = h[a]`, else `0`
- **Author Modifications** — `n_{H,o,a} := Σ_{h∈H} 𝕀(a,h) · 𝕀ⁿ(h,o)` — commits by `a` that changed `o`
- **Author Churn** — `λ_{H,o,a} := Σ_{h∈H} λ_{h,o} · 𝕀(a,h)` — churn on `o` from commits by `a`
- **Author Ownership** — `ω_{H,o,a} := λ_{H,o,a} / λ_{H,o}` if `λ_{H,o} ≠ 0`, else `0` (fraction of churn)

---

## 5. Rubric & Grading (brief §3)

**Weights:** Requirements 50% · Architectural & UI Design 25% · Usability 25%
**Tiers are cumulative** (a tier is only reachable if the previous is satisfied) and each tier is
judged **holistically**.

### 5.1 Requirements (50%)
| Tier | Bar |
|------|-----|
| ≤ 25% | Correct metrics for **some** categories (repo / file / directory / set / author) · ingestion via **either** zip **or** URL |
| ≤ 50% | Correct metrics for **all** categories · ingestion via **both** zip **and** URL |
| ≤ 75% | Additionally implements **at least one of**: Filtering, Author Merge, Multi-repo support |
| ≤ 100% | Implements **all of**: Filtering, Author Merge, Multi-repo support |

### 5.2 Architectural & UI Design (25%)
| Tier | Bar |
|------|-----|
| ≤ 25% | Redundant & slow metric computation, poor visualisation |
| ≤ 50% | Reasonable metric computation, okay visualisation |
| ≤ 75% | Efficient algorithms for metric computation, good visualisation |
| ≤ 100% | Efficient algorithms **and architecture** for metric computation, inspired visualisation |

### 5.3 Usability (25%)
| Tier | Bar |
|------|-----|
| ≤ 25% | Poor navigation, no error handling, slow on small (~1,000 commits) repos, no QoL features |
| ≤ 50% | Okay navigation, minimal error handling, okay on small repos, slow on medium (~10,000 commits), minimal-to-none QoL |
| ≤ 75% | Good navigation, error handling, good performance on medium repos, QoL features |
| ≤ 100% | Excellent navigation, good performance on large (~100,000 commits) repos |

### 5.4 Test repositories (metric correctness judged against these)
| Repo | URL | Approx. scale (rubric tier) |
|------|-----|------------------------------|
| cJSON | https://github.com/DaveGamble/cJSON.git | small (~1k commits) |
| Redis | https://github.com/redis/redis.git | medium (~10k commits) |
| Git | https://github.com/git/git.git | large (~60k+ commits, < 100k) |

Sample metrics for each repo will be provided from a specific commit hash — our output must match.

> The brief carries an "AI Declaration" note (the brief itself was AI-reviewed). Check whether our
> submission needs an equivalent AI-usage declaration. `[CONFIRM]`

### 5.5 Feature priority & abandonment order (rubric-driven · 2026-10-06)

**Score arithmetic first** (Requirements = 50% of total; tier band × weight):
- All 5 metric categories correct + both ingestion forms → up to **25% of total grade**
- + any ONE of {Filtering, Author Merge, Multi-repo} → up to **37.5%** (first tier-3 feature = +12.5 pts)
- + all THREE → up to **50%** (2nd + 3rd tier-3 features *combined* = only +12.5 pts)

So beyond the core, the *first* tier-3 feature is worth as much as the other two combined —
and Architecture (25%) + Usability (25%) together outweigh the entire tier-3 checklist.

**⚠ Notation trap:** the brief's feature list names only 4 metric categories, but the rubric
requires **five** — "(repo, file, directory, set, **author**)" — for the ≤50% band. Author
*metrics* (per-identity) are mandatory; Author *Merging* (identity resolution) is the separate
tier-3 feature.

**Importance ranking (grade impact):**

| Rank | Feature | Rubric basis | Notes |
|---|---|---|---|
| 1 | Metric categories (file, directory, repo, commit set, author) | Gates ≤50% band; also drives Architecture (efficient computation) & Usability (performance tiers) | Only feature touching **all three criteria** = 100% of grade |
| 2 | Ingestion — BOTH zip AND clone URL | "Both" gates ≤50% band; "either" caps at ≤25% | Each form is trivial plumbing — never a sensible cut |
| 3 | Filtering | Tier-3 feature | Product-defining (§1: "dashboard should be filterable by…"); makes commit-set metrics demonstrable; feeds Usability/QoL |
| 4 | Multi-repo support | Tier-3 feature | Cheapest tier-3 if `repo_id` is designed into the schema from day 1; overlaps with "filter by repository" |
| 5 | Author Merging | Tier-3 feature | Mailmap part is cheap (parse + alias map); **manual merge UI is the expensive part** |

**Complexity:**

| Feature | Complexity | Where the cost is |
|---|---|---|
| Metric categories | **High base / ~zero marginal** | One shared engine: history walk + rename (-M50) + binary + deletions + per-commit per-file `l⁺`/`l⁻`. After that, dir/repo/set/author categories are pure aggregation — cutting a category saves ~nothing |
| Zip ingestion | Low | upload → unzip → verify `.git` |
| Clone URL | Low | deep `git clone` |
| Multi-repo | Low–moderate | repo selector + registry; ~free if schema is multi-repo from the start |
| Filtering | Moderate | time/author/path filters are cheap queries over precomputed data; **manual commit-list picker** is the UI-expensive part |
| Author Merging | Moderate–high | mailmap parsing cheap; manual merge UI + re-aggregation semantics expensive |

**Abandonment order (drop first → last) under time pressure:**

1. **Author Merging — manual merge UI** (keep mailmap ingestion if cheap: parse + apply alias
   map at aggregation time). Only needed for the 100% band, and only *together with* both other
   tier-3 features.
2. **Multi-repo — UI only** (keep the multi-repo data model regardless: retrofitting is painful,
   and the registry falls out of ingestion anyway).
3. **Filtering — manual commit-list picker** (keep time-period, author, and file/dir filters:
   cheap, high Usability value, and they make commit-set metrics visible in the dashboard).
4. **Never abandon:** the metric engine (correctness + efficiency), both ingestion forms, and the
   metric categories. Cutting any category is a false economy (marginal cost ≈ 0 once the engine
   exists) and caps Requirements at the ≤25% band; dropping either ingestion form does the same.

**Strategic read:** the rubric pays for an *efficient, correct engine* plus a *good dashboard*
(50% combined) far more than for the tier-3 feature checklist (max 25%). Effort split target:
~60% engine · ~25% dashboard/UX · ~15% tier-3 features, built in the order multi-repo
(designed-in) → filtering-lite → author merge (mailmap first, manual UI last). If a metric
category fails validation late in the day, the last-resort fallback is shipping only the
categories that validate (the ≤25% band allows "some categories"), with correctness priority:
file → directory → repo (root) → commit set → author.

---

## 6. Architecture Map

**Tech stack (decided 2026-10-06):** Python 3.10+ with git CLI subprocess wrapper. No external dependencies. Package layout: `src/rat_metric_engine/`.

```
┌────────────────────────────────────────────────────────────────┐
│                       RAT Web Dashboard                        │
│  Multi-repo views · Filters (repo / author / file/dir / time / │
│  commit list) · Author merge UI · Metric visualisations        │
└──────────────────────────────┬─────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────┐
│                     Analysis / Metric Engine                    │
│  git history traversal (non-merge, reachable from ref) ·       │
│  per-commit diffs w/ rename detection (-M50%) & binary filter ·│
│  mailmap + manual author identity resolution ·                  │
│  metric aggregation (file → dir → repo) · commit-set queries    │
└───────────────┬──────────────────────────────┬─────────────────┘
               │                              │
┌──────────────▼─────────────┐  ┌─────────────▼─────────────────┐
│      Ingestion Layer       │  │        Storage / Registry      │
│  zip upload (w/ .git) ·    │  │  repo registry (multi-repo) ·  │
│  URL → deep clone         │  │  precomputed metrics & metadata │
└────────────────────────────┘  └─────────────────────────────────┘
```

**Implemented (2026-10-06):** Base metric engine (`rat_metric_engine`) with streaming git history traversal, per-commit numstat extraction, binary filtering, deletion/rename handling, TSV/JSONL output, and aggregation layers for file, directory, repository, commit-set, and author metrics. CLI entry point: `rat-metric-engine <repo>`.

### Key architectural implications (drive the "efficient" rubric tiers)
1. **Compute once at ingestion, not per request** — filters (author, time, commit subset) must be
   answerable from precomputed per-commit/per-object data; never re-walk full history per query.
2. **Single pass over history** per repo: walk non-merge commits once, emit per-commit per-object
   deltas (added/removed), then all aggregations are sums/group-bys over that base data.
3. **Scaling target < 100k commits** (git.git) → ingestion is the expensive step; must be
   streaming/batched, with cheap per-commit stats (e.g. numstat-style) rather than full diffs.
4. **Author merging must be re-appliable** without recomputing raw diffs — keep raw per-author
   data keyed by original identity, merge at the aggregation layer.
5. **Deletion & rename semantics** must be handled in the base delta extraction (§3), since every
   higher metric depends on them being right.

---

## 7. Current Project State

```
SDP_Test1/
├── COMS3011A Test - test_brief.pdf   # original brief (authority for formulas)
├── COMS3011A Test - test_brief.md    # converted brief (token-efficient reference)
├── PROJECT_STRUCTURE.md               # THIS document — living context map
├── README.md                          # placeholder (currently just "# SDP_Test1")
├── pyproject.toml                     # Python packaging + pytest config (rat-metric-engine)
├── src/
│   └── rat_metric_engine/
│       ├── __init__.py                # public API: MetricEngine, FileDelta, aggregation, writers
│       ├── aggregation.py             # file/dir/repo/commit-set/author metric aggregation
│       ├── engine.py                  # git history walk + numstat delta extraction + author metadata
│       └── cli.py                     # CLI: rat-metric-engine <repo> [--ref --format --output]
├── tests/
│   └── test_metric_engine.py          # fixture repo covering initial/delete/binary/rename
└── docs/                              # implementation plans (one per feature)
    ├── README.md                      # overview + dependency graph + build order
    ├── 01-metric-engine.md            # base extraction (history walk, rename, binary, deletions, l⁺/l⁻)
    ├── 02-metric-categories.md        # aggregation layers (file/dir/repo/set/author metrics)
    ├── 03-ingestion.md                # zip upload + URL clone
    ├── 04-multi-repo.md               # multi-repo support (schema, registry, UI)
    ├── 05-filtering.md                # filtering dimensions (time, author, path, commits, manual list)
    ├── 06-author-merging.md           # author merging (mailmap + manual merge UI)
    ├── 07-dashboard.md                # dashboard UI (visualisation, navigation, QoL)
    └── 08-validation.md               # validation harness (test repos, sample metrics, benchmarking)
```

**Status:** Base metric engine (01) and aggregation layers (02) implemented and tested. Ingestion (03) is next.

### Progress log
| Date | Update |
|------|--------|
| 2026-10-06 | Created context map from brief §1 (overview) + §3 (rubric). Metrics held at summary level pending deep-dive go-ahead. |
| 2026-10-06 | Verified every formula against the original PDF (rendered pages as images). Notation corrected to the brief's `h`/`H` style; churn rate denominator confirmed as commit-set size; authorship test `𝕀(a,h)` confirmed; all `[CONFIRM vs PDF]` items resolved and removed. |
| 2026-10-06 | Added §5.5 — rubric-driven feature priority, complexity & abandonment order (decision framework for time pressure). Key insight: metric categories share one engine (marginal cost ≈ 0); tier-3 features are the intended flex room. |
| 2026-10-06 | Created `docs/` directory with 8 implementation plan files (one per feature) + README. Each file breaks the feature into sub-tasks with dependencies, approach, and acceptance criteria. Build order: 01 → 08. |
| 2026-10-06 | Tech stack decision: Python 3.10+ with git CLI subprocess wrapper. Package layout: `src/rat_metric_engine/` with `engine.py` (core), `cli.py` (entry point), `__init__.py` (public API). No external dependencies. |
| 2026-10-06 | Implemented metric engine base extraction (01-metric-engine.md): git history traversal (non-merge, oldest-first topo order), per-commit diff extraction via `git diff-tree --numstat -M50`, binary file filtering, deletion handling, rename handling (including brace-form paths), initial commit handling via `--root`, streaming TSV/JSONL output. |
| 2026-10-06 | Added CLI entry point: `rat-metric-engine <repo> [--ref HEAD] [--repo-id <id>] [--format tsv|jsonl] [--output <path>]`. Supports stdout or file output. |
| 2026-10-06 | Added fixture-based unit tests covering: numstat parsing (binary skip, rename normalization), history traversal order, initial commit deltas, deletion deltas, binary exclusion, pure rename (l⁺=l⁻=0), rename-with-edit deltas, TSV/JSONL output format. All 4 tests pass. |
| 2026-10-06 | Implemented metric categories (02-metric-categories.md): file metrics with growth/churn, recursive directory rollups, repository root metrics, commit-set sums/modification frequency/churn rate, author modifications/churn/ownership, and public API exports. Added author metadata extraction to `CommitInfo`; all 8 tests pass. |

---

## 8. Open Questions / To Confirm

*Resolved 2026-10-06 (verified against the PDF): churn rate denominator (commit-set size `|H|`), authorship test notation, growth over a commit set = Σ per-commit growth, merge commits fully excluded from analysis via `H̄`.*

*Resolved 2026-10-06 (tech stack): Python 3.10+ with git CLI subprocess wrapper. No external dependencies. Package layout: `src/rat_metric_engine/`. CLI entry point via `pyproject.toml`.*

1. Whether our submission requires an AI-usage declaration (the brief itself carries one: "Claude Web (Opus 5.5) - reviewed").
2. Sample metrics for the three test repos (provided by lecturer "from a specific commit hash") — needed to build the validation harness; not yet received.
3. Reference commit `h_r` selection: brief says "specified reference commit (typically HEAD)" — decide whether users can pick a different reference/branch.

---

## 9. Next Steps (proposed order)

1. ✅ **Metrics deep-dive** — exact formulas already captured & PDF-verified (2026-10-06). Implementation semantics resolved during engine build.
2. ✅ Tech stack & architecture decision — Python 3.10+ with git CLI subprocess wrapper (2026-10-06).
3. ✅ Scaffold project; implement base delta extraction (rename/binary/deletion semantics) — **completed 2026-10-06**.
4. **Build up metric aggregation layers** (file → directory → repository; commit sets; authors) — next priority (02-metric-categories.md).
5. Ingestion (zip + URL), multi-repo registry.
6. Dashboard UI + filtering; author merge (mailmap + manual).
7. Validation against cJSON → Redis → Git sample metrics (performance tiers in that order).
