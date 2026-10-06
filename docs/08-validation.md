# 08 — Validation Harness

> **Purpose:** Validate metric correctness against provided sample metrics for test repos (cJSON,
> Redis, Git), and benchmark performance.
>
> **Rubric basis:** Metric correctness is judged against test repos. Performance tiers (~1k/~10k/~100k
> commits) drive the Usability criterion.
>
> **Complexity:** Moderate. Needs all other features to be functional.

## Sub-tasks

### 8.1 Test repo setup
**What:** Clone cJSON, Redis, Git to specific commit hashes (provided by lecturer).

**How:**
- Clone repos: `git clone <url> <dir>`
- Checkout specific commit: `git checkout <commit_hash>`
- Store commit hashes (provided by lecturer) in a config file
- Verify repos are at correct commits

**Dependencies:** 03-ingestion (clone functionality)

**Acceptance:** Test repos are cloned and checked out to correct commits.

---

### 8.2 Sample metrics
**What:** Load provided sample metrics (from lecturer) for comparison.

**How:**
- Sample format: TBD (CSV/JSON with expected metric values)
- Load samples into a comparison dataset: `(repo_id, commit_hash, object, metric_name, expected_value)`
- Store samples in a file or database table

**Dependencies:** None (but samples must be provided by lecturer)

**Acceptance:** Sample metrics are loaded and queryable.

---

### 8.3 Comparison
**What:** Compute metrics on test repos, compare against samples.

**How:**
- For each test repo and commit hash:
  - Run metric engine (01) and aggregation (02)
  - Query computed metrics for specified objects
  - Compare against sample metrics
- Tolerance: floating-point metrics (churn rate, ownership) allow small epsilon (e.g., 1e-6)
- Integer metrics (l⁺, l⁻, modifications) must match exactly
- Report: pass/fail per metric, per object, per repo

**Dependencies:** 01-metric-engine, 02-metric-categories, 8.1, 8.2

**Acceptance:** Computed metrics match sample metrics within tolerance.

---

### 8.4 Validation report
**What:** Show pass/fail per metric, per repo, per commit hash.

**How:**
- Report format: table or dashboard view
- Columns: `repo`, `commit_hash`, `object`, `metric_name`, `expected`, `computed`, `status` (pass/fail)
- Summary: total pass/fail count, pass rate %
- Filter: by repo, by metric name, by status
- Export: download report as CSV/JSON

**Dependencies:** 8.3 (comparison), 07-dashboard (UI for report)

**Acceptance:** Validation report shows pass/fail clearly; can filter and export.

---

### 8.5 Performance benchmarking
**What:** Measure ingestion, metric computation, and query times on each test repo.

**How:**
- Metrics to measure:
  - Ingestion time (03): zip extract or URL clone duration
  - Metric engine time (01): history walk + diff extraction duration
  - Aggregation time (02): directory/commit-set/author metric computation duration
  - Query time (05): filtered metric query duration
- Benchmark script: run each step, record duration, output summary
- Performance tiers (Usability rubric):
  - Small (~1,000 commits): cJSON — should be fast (< 1 minute ingestion, < 1 second queries)
  - Medium (~10,000 commits): Redis — should be okay (< 5 minutes ingestion, < 5 second queries)
  - Large (~100,000 commits): Git — should be good (< 10 minutes ingestion, < 10 second queries)

**Dependencies:** 01-metric-engine, 02-metric-categories, 03-ingestion, 05-filtering

**Acceptance:** Performance meets rubric tiers for test repos.

---

## Implementation Notes

- **Sample metrics:** Not yet received from lecturer. This feature is blocked until samples are provided.
- **Tolerance:** Floating-point comparisons need epsilon (e.g., 1e-6 for churn rate, ownership).
- **Automation:** Validation should be automated (script or CI pipeline) for repeatability.
- **Performance baselines:** Record baselines for each test repo; track regressions.

---

## Acceptance Criteria

- [ ] Test repos are cloned to correct commits
- [ ] Sample metrics are loaded (once provided)
- [ ] Computed metrics match sample metrics within tolerance
- [ ] Validation report shows pass/fail clearly
- [ ] Can filter and export validation report
- [ ] Performance meets rubric tiers (small/medium/large repos)
- [ ] Benchmark script outputs summary
