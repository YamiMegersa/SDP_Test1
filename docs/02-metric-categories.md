# 02 — Metric Categories (Aggregation Layers)

> **Purpose:** Compute all metric categories (file, directory, repository, commit set, author)
> on top of the per-commit per-file deltas from the metric engine.
>
> **Rubric basis:** "Correct for all metrics" gates the ≤50% Requirements band (50% weight).
>
> **Complexity:** Low (after 01). Pure aggregation over engine output — marginal cost ≈ 0.

## Sub-tasks

### 2.1 File metrics
**What:** `l⁺_{h,f}`, `l⁻_{h,f}`, `δ_{h,f}`, `λ_{h,f}` per commit per file.

**How:**
- Direct from engine output (01): `l⁺` and `l` are already extracted
- `δ_{h,f} := l⁺_{h,f} − l_{h,f}` (growth = net change)
- `λ_{h,f} := l⁺_{h,f} + l⁻_{h,f}` (churn = changed lines)

**Dependencies:** 01-metric-engine (per-commit per-file deltas)

**Acceptance:** For a test commit, file metrics match expected values.

---

### 2.2 Directory metrics
**What:** `l⁺_{h,d}`, `l⁻_{h,d}`, `δ_{h,d}`, `λ_{h,d}` per commit per directory.

**How:**
- Recursive aggregation over **immediate** children (files `f ∈ d`, subdirectories `d' ∈ d`):
  - `l_{h,d} := Σ_{f∈d} l⁺_{h,f} + Σ_{d'∈d} l⁺_{h,d'}`
  - `l⁻_{h,d} := Σ_{f∈d} l⁻_{h,f} + Σ_{d'∈d} l⁻_{h,d'}`
  - `δ_{h,d} := Σ_{f∈d} δ_{h,f} + Σ_{d'∈d} δ_{h,d'}`
  - `λ_{h,d} := Σ_{f∈d} λ_{h,f} + Σ_{d'∈d} λ_{h,d'}`
- For each commit `h`, build directory tree from file paths, roll up from leaves to root
- Directory membership: `f` is in `d` if `f` is an immediate child of `d` in `h[F]` or `h[p][F]`

**Dependencies:** 2.1 (file metrics)

**Acceptance:** For a test commit, directory metrics match expected values (sum of immediate children).

---

### 2.3 Repository metrics
**What:** Directory metrics at the root.

**How:**
- Trivial once 2.2 works: repository metrics = directory metrics for `d = root`
- Root directory contains all top-level files and subdirectories

**Dependencies:** 2.2 (directory metrics)

**Acceptance:** Repository metrics = root directory metrics.

---

### 2.4 Commit set metrics
**What:** `l⁺_{H,o}`, `l⁻_{H,o}`, `δ_{H,o}`, `λ_{H,o}`, `n_{H,o}`, `η_{H,o}`, `ρ_{H,o}` for object `o ∈ H[F] ∪ H[D]`.

**How:**
- Added/Removed/Growth/Churn over commit set `H`:
  - `l⁺_{H,o} := Σ_{h∈H} l⁺_{h,o}`
  - `l⁻_{H,o} := Σ_{h∈H} l⁻_{h,o}`
  - `δ_{H,o} := Σ_{h∈H} δ_{h,o}`
  - `λ_{H,o} := Σ_{h∈H} λ_{h,o}`
- Modification indicator: `𝕀ⁿ(h,o) := 1` if `λ_{h,o} > 0`, else `0`
- **Modifications**: `n_{H,o} := Σ_{h∈H} 𝕀ⁿ(h,o)` — # commits with at least some change on `o`
- **Modification Frequency**: `η_{H,o} := n_{H,o} / |H|` if `|H| ≠ 0`, else `0`
- **Churn Rate**: `ρ_{H,o} := λ_{H,o} / |H|` if `|H| ≠ 0`, else `0`
- Filter commits by `H` (time window, manual list, etc.), then sum

**Dependencies:** 2.1, 2.2 (file and directory metrics per commit)

**Acceptance:** For a test commit set `H`, metrics match expected values.

---

### 2.5 Author metrics
**What:** `n_{H,o,a}`, `λ_{H,o,a}`, `ω_{H,o,a}` for author `a` on object `o`.

**How:**
- Authorship test: `𝕀(a,h) := 1` if `a = h[a]`, else `0`
- **Author Modifications**: `n_{H,o,a} := Σ_{h∈H} 𝕀(a,h) · 𝕀ⁿ(h,o)` — commits by `a` that changed `o`
- **Author Churn**: `λ_{H,o,a} := Σ_{h∈H} λ_{h,o} · 𝕀(a,h)` — churn on `o` from commits by `a`
- **Author Ownership**: `ω_{H,o,a} := λ_{H,o,a} / λ_{H,o}` if `λ_{H,o} ≠ 0`, else `0` — fraction of churn
- Join with author identity (from commit metadata), then aggregate per `(author, object)`

**Dependencies:** 2.4 (commit set metrics), commit author metadata (from 01)

**Acceptance:** For a test author and object, metrics match expected values.

---

### 2.6 Aggregation strategy
**What:** Decide whether to precompute aggregates or compute on demand.

**How:**
- **Option A (precompute):** After 01, compute all aggregates (2.2, 2.4, 2.5) and store. Fast queries, slower ingestion.
- **Option B (on-demand):** Store only per-commit per-file deltas (01), compute aggregates at query time. Fast ingestion, slower queries.
- **Recommendation:** Hybrid — precompute per-commit aggregates (2.2), compute commit-set and author metrics on demand (2.4, 2.5) since they depend on filter parameters.
- For performance at scale (git.git ~60k commits), precompute what you can.

**Dependencies:** 2.1, 2.2, 2.4, 2.5

**Acceptance:** Aggregation strategy documented; performance acceptable for test repos.

---

## Implementation Notes

- **Tech stack TBD:** Aggregation can be done in SQL (if using a database) or in application code.
- **Directory tree construction:** For each commit, build a tree from file paths, then roll up.
- **Commit set filtering:** Apply filter (time, author, manual list) to commit set `H`, then aggregate.
- **Author identity:** Use `h[a]` from commit metadata; author merging (06) applies an alias map on top.
- **Performance:** For large repos, precompute per-commit directory aggregates (2.2) to avoid recomputing the tree for every query.

---

## Acceptance Criteria

- [x] File metrics (`l⁺`, `l⁻`, `δ`, `λ`) correct for test commits
- [x] Directory metrics = sum of immediate children (files + subdirectories)
- [x] Repository metrics = root directory metrics
- [x] Commit set metrics (sums over `H`) correct for test commit sets
- [x] Modification frequency `η = n/|H|` correct
- [x] Churn rate `ρ = λ/|H|` correct
- [x] Author metrics (modifications, churn, ownership) correct for test authors
- [x] Aggregation strategy documented and performant for test repos
