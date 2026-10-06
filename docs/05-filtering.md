# 05 — Filtering

> **Purpose:** Filter metrics by repository, author, file/directory, commits, time period, or
> manually selected commit list. Makes commit-set metrics demonstrable and feeds Usability/QoL.
>
> **Rubric basis:** Tier-3 feature (75%/100% band of Requirements). Product-defining per brief §1.
>
> **Complexity:** Moderate. Cheap parts (time/author/path filters) are queries over precomputed data;
> manual commit-list picker is UI-expensive.

## Sub-tasks

### 5.1 Time period filter (`H_t`, `H_{i,j}`)
**What:** Filter commits by committer date: from timestamp `t` to present (`H_t`), or from `i` to `j` exclusive (`H_{i,j}`).

**How:**
- Store `committer_date` (UNIX timestamp) per commit (from 01.1)
- Time filter: `WHERE committer_date >= t` (for `H_t`) or `WHERE committer_date >= i AND committer_date < j` (for `H_{i,j}`)
- UI: date range picker (calendar widget or timestamp input)
- Apply filter to commit set `H` before aggregating metrics (02.4)

**Dependencies:** 01.1 (commit metadata with committer_date), 02.4 (commit set metrics)

**Acceptance:** Filtering by time period returns correct commit set and metrics.

---

### 5.2 Author filter
**What:** Filter commits/metrics by author identity (post-merge).

**How:**
- Store `author_email` and `author_name` per commit (from 01.1)
- After author merging (06), use canonical author identity
- Filter: `WHERE author_id = <selected_author>`
- UI: author dropdown (populated from distinct authors in repo)
- Apply filter to commit set `H` or to author metrics (02.5)

**Dependencies:** 01.1 (commit author metadata), 06-author-merging (for canonical identities)

**Acceptance:** Filtering by author returns correct commits and author-scoped metrics.

---

### 5.3 File/directory filter
**What:** Filter metrics by file path or directory path (prefix match or exact match).

**How:**
- File filter: `WHERE file_path = <exact_path>` or `WHERE file_path LIKE '<prefix>%'` (for directory)
- Directory filter: `WHERE dir_path = <exact_path>` or `WHERE dir_path LIKE '<prefix>%'`
- UI: path input with autocomplete (populated from distinct paths in repo)
- Breadcrumb navigation: click through directory tree to drill down

**Dependencies:** 01.2 (file paths from diff extraction), 02.2 (directory metrics)

**Acceptance:** Filtering by file/dir path returns correct metrics for that path.

---

### 5.4 Commit filter (by hash or range)
**What:** Filter by specific commit hash or commit range.

**How:**
- Commit hash filter: `WHERE commit_hash = <hash>` or `WHERE commit_hash IN (<hash1>, <hash2>, ...)`
- Commit range: `WHERE commit_hash BETWEEN <start> AND <end>` (topological order)
- UI: commit hash input, or commit range selector (start/end commits)
- Apply filter to commit set `H`

**Dependencies:** 01.1 (commit hashes)

**Acceptance:** Filtering by commit hash/range returns correct metrics.

---

### 5.5 Manual commit list
**What:** UI to select an arbitrary list of commits, compute metrics over that subset.

**How:**
- UI: multi-select list of commits (checkboxes or shift-click), or paste commit hashes
- Store selected commit hashes in session/state
- Filter: `WHERE commit_hash IN (<selected_hashes>)`
- Apply filter to commit set `H` for metric aggregation (02.4)

**Dependencies:** 01.1 (commit hashes), 02.4 (commit set metrics)

**Acceptance:** Can select arbitrary commits and compute metrics over that subset.

---

### 5.6 Filter composition (AND logic)
**What:** Combine multiple filters (time + author + path + commits) with AND logic.

**How:**
- Compose WHERE clauses: `WHERE committer_date >= t AND author_id = a AND file_path LIKE 'src/%' AND commit_hash IN (...)`
- UI: show active filters as chips/tags, allow removing individual filters
- "Clear all filters" button
- Filter state persisted in URL query params (for shareability) or session

**Dependencies:** 5.1, 5.2, 5.3, 5.4, 5.5

**Acceptance:** Multiple filters can be applied simultaneously; results are intersection of all filters.

---

### 5.7 Filter UI (selectors, apply/clear, active filter display)
**What:** User interface for all filter dimensions.

**How:**
- Filter panel: sidebar or top bar with selectors for each dimension
  - Time: date range picker
  - Author: dropdown
  - File/dir: path input with autocomplete
  - Commits: hash input or range selector
  - Manual list: multi-select or paste
- Apply button: apply selected filters
- Clear button: reset all filters
- Active filter display: show applied filters as chips/tags
- Filter count: show number of active filters

**Dependencies:** 07-dashboard (UI framework), 5.1-5.6

**Acceptance:** Filter UI is intuitive; filters can be applied, cleared, and composed.

---

## Implementation Notes

- **Performance:** Filters should be applied to precomputed data (02), not re-walk history (01).
- **Indexing:** Database indexes on `(repo_id, committer_date)`, `(repo_id, author_id)`, `(repo_id, file_path)` are essential.
- **URL state:** Filter state in URL query params allows sharing/bookmarking filtered views.
- **Manual commit list:** Most UI-expensive part; consider simplifying (e.g., paste hashes only, no multi-select UI).

---

## Implementation Status

Implemented (2026-10-06): all filter dimensions are query-param-driven aggregations over the
precomputed per-commit object metrics — never a re-walk of history, per the engine's own
"compute once at ingestion" rule.

- **Time (5.1):** `start_date`/`end_date` (`YYYY-MM-DD`) on the dashboard map to `H_t`/`H_{i,j}`
  (`i` inclusive, `j` exclusive — the UI's inclusive "to date" is converted to the start of the
  next day internally).
- **Author (5.2):** `author` restricts H to one post-merge identity; the dropdown is populated
  from `distinct_authors()` over the repo's raw metrics.
- **File/directory (5.3):** `path` matches a file exactly or anything under a directory prefix.
  Deliberately does **not** shrink `|H|` — only time/author/commit filters affect the
  modification-frequency/churn-rate denominator; path only narrows which objects are reported.
- **Commit hash/range (5.4) and manual commit list (5.5):** both use the same `commit_hashes`
  mechanism (`aggregate_commit_set`/`aggregate_author_metrics`); the dashboard's `commits` field
  accepts comma/whitespace-separated hashes (simplified per this file's own note — paste only,
  no multi-select UI).
- **Composition (5.6):** all filters AND together naturally since they're applied in one pass
  over the metrics; verified via `test_filters_compose_with_and_logic`.
- **UI (5.7):** `repo_metrics.html` has a filter panel (date range, author dropdown, path input,
  commits input), active-filter chips with individual remove links, a "Clear all filters" button,
  and filter state lives entirely in URL query params (shareable/bookmarkable). An "Authors" tab
  was added to the dashboard to make the previously backend-only author metric category
  demonstrable in the UI.

Implementation: `aggregation.py` (`aggregate_commit_set`/`aggregate_author_metrics` gained
`author`/`path` params plus `distinct_authors()`), `web.py` (`parse_filters`, `load_object_metrics`,
filtered `repo_metrics` + `api_get_metrics` routes), `templates/repo_metrics.html`. Also fixed a
pre-existing template bug (`{% set x = [m for m in ... if ...] %}` is invalid Jinja2 — no list
comprehensions — rewritten with `selectattr(...)|list`) found while adding web test coverage.

Tests: `tests/test_filtering.py` (aggregation-layer unit tests for each filter dimension plus
composition and the `|H|`-not-shrunk-by-path invariant) and `tests/test_web.py` (Flask test-client
end-to-end tests driving the dashboard routes and the filtered JSON API).

## Acceptance Criteria

- [x] Time period filter works (`H_t`, `H_{i,j}`)
- [x] Author filter works
- [x] File/directory filter works (exact and prefix match)
- [x] Commit hash/range filter works
- [x] Manual commit list selection works
- [x] Filters can be composed (AND logic)
- [x] Active filters are displayed as chips/tags
- [x] Filters can be cleared individually or all at once
- [x] Filter state is persisted (URL or session)

