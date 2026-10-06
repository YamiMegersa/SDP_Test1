# 07 — Dashboard UI

> **Purpose:** Web-app dashboard for viewing metrics, with visualisations, navigation, and QoL
> features. Cross-cutting: can be built incrementally alongside other features.
>
> **Rubric basis:** Architecture & UI Design (25% weight) + Usability (25% weight) = 50% of grade.
> "Inspired visualisation" and "excellent navigation" at 100% tier.
>
> **Complexity:** High. UI/UX work is inherently iterative; visualisation quality is subjective.
>
**Current State (2026-10-06):** Dashboard substantially complete. Flask + Bootstrap 5 + DataTables + full filtering UI + author merging UI. 53 tests passing. Remaining work: metric visualisations (charts/treemaps), author visualisations, navigation polish, performance optimisation, QoL features.

## Current Implementation (Completed)

**Tech Stack:**
- Backend: Flask 3.0+ with Jinja2 templates
- Frontend: Bootstrap 5 + Bootstrap Icons + DataTables
- Server: Development server (run_dashboard.py)

**Routes Implemented:**
- `GET /` — Repository list with status badges (ingesting/ready/failed)
- `GET /ingest` — Ingestion form (zip upload + URL clone tabs)
- `POST /ingest/zip` — Handle zip file upload
- `POST /ingest/url` — Handle URL clone
- `GET /repo/<repo_id>` — Repository status page with live updates
- `GET /repo/<repo_id>/metrics` — Metric tables with filtering (time/author/path/commits)
- `GET /repo/<repo_id>/authors` — Author merge management page
- `POST /repo/<repo_id>/authors/merge` — Merge selected author identities
- `POST /repo/<repo_id>/authors/unmerge` — Undo a single alias merge
- `GET /api/repos` — JSON API for repo list
- `GET /api/repos/<repo_id>` — JSON API for repo metadata
- `GET /api/repos/<repo_id>/metrics` — JSON API for filtered metrics

**Templates:**
- `base.html` — Bootstrap 5 layout with navbar
- `index.html` — Repository list with cards (status, commit count, metric count)
- `ingest.html` — Tabbed ingestion form (zip/URL)
- `repo.html` — Repository status with auto-refresh during ingestion
- `repo_metrics.html` — Filter panel + summary cards + tabbed metric tables (files/dirs/repo/authors) with DataTables
- `authors.html` — Author merge management (select aliases, choose canonical, un-merge)

**Features Working:**
- ✅ Responsive Bootstrap 5 layout
- ✅ Repository list with status indicators
- ✅ Ingestion forms (zip + URL)
- ✅ Live status updates (auto-refresh)
- ✅ Sortable/paginated metric tables (DataTables)
- ✅ Summary cards (commits, metrics, churn, growth)
- ✅ Tabbed interface (files, directories, repository, authors)
- ✅ Error handling for failed ingestions
- ✅ JSON API endpoints
- ✅ Filtering UI (date range, author dropdown, path, commit hashes, active filter badges)
- ✅ Click-to-filter icons on paths and authors in tables
- ✅ Author merging UI (merge aliases, custom canonical, un-merge, mailmap-aware)
- ✅ Author metrics tab (modifications, churn, ownership %)
- ✅ Filter composition (AND logic across all dimensions)

---

## Sub-tasks (Remaining Work)

### 7.1 Dashboard layout (multi-repo views, metric tables)
**Status:** ✅ **COMPLETED** (minimal version)

**What:** Overall page structure: repo selector, metric tables, filter panel.

**Current Implementation:**
- ✅ Header with navigation (Home, Ingest)
- ✅ Repository list with cards and status badges
- ✅ Metric tables with DataTables (sortable, paginated)
- ✅ Empty state ("Add Your First Repository" prompt)
- ✅ Responsive Bootstrap 5 layout

**Remaining:**
- ⏳ Repo selector dropdown in header (currently using card-based list)
- ⏳ Sidebar layout for filter panel (currently no filter UI)

**Dependencies:** 04-multi-repo (✅ done), 05-filtering (✅ done)

**Acceptance:** ✅ Dashboard layout is clean and functional; metric tables display data.

---

### 7.2 Metric visualisation (charts, heatmaps, treemaps)
**Status:** ⏳ **NOT STARTED**

**What:** Visual representations of metrics for quick insight.

**How:**
- File/dir metrics: bar charts (top files by churn), treemaps (directory structure sized by churn)
- Commit set metrics: time series (churn over time), line charts (growth trend)
- Repository metrics: summary cards (✅ already done), add more detailed charts
- Visualisation library: Chart.js (CDN-based, simple integration)
- Interactive: hover for details, click to drill down

**Implementation Plan:**
1. Add Chart.js CDN to base.html
2. Create chart templates/components
3. Add routes to compute time-series data (churn over time)
4. Add top-N charts (files by churn, dirs by growth)
5. Add treemap for directory structure (D3.js or Chart.js plugin)

**Dependencies:** 02-metric-categories (✅ done), 05-filtering (✅ done, need UI)

**Acceptance:** Metrics are visualised clearly; charts are interactive.

---

### 7.3 Author visualisation (contribution charts, ownership pies)
**Status:** ⏳ **PARTIALLY COMPLETE** (table done, charts not started)

**What:** Visual representations of author metrics.

**Current Implementation:**
- ✅ Author metrics tab in repo_metrics.html with sortable DataTables
- ✅ Table columns: author, modifications, author churn, total churn, ownership %
- ✅ Click-to-filter funnel icon on each author row
- ✅ Author metrics respect active filters (time, path, commits)
- ✅ Author metrics respect merged identities (from 06)

**Remaining:**
- ⏳ Bar chart (churn by author)
- ⏳ Pie chart (ownership %)
- ⏳ Stacked area chart (churn over time by author)

**How:**
- Add Chart.js CDN to base.html
- Create chart containers in authors tab
- Compute per-author time-series data in route
- Render charts from JSON data

**Dependencies:** 02.5 author metrics (✅ done), 06-author-merging (✅ done)

**Acceptance:** Author metrics are visualised clearly; can filter by author.

---

### 7.4 Navigation (repo selector, filter panel, breadcrumb)
**Status:** ⏳ **PARTIALLY COMPLETE**

**What:** Intuitive navigation between repos, filters, and metric views.

**Current Implementation:**
- ✅ Navbar with Home and Ingest links
- ✅ Back buttons on detail pages
- ✅ Repository list as main navigation hub
- ✅ URL state for filters (query params — shareable/bookmarkable)
- ✅ Cross-page navigation (repo status → metrics → authors → back)

**Remaining:**
- ⏳ Repo selector dropdown in header (quick switch between repos without going home)
- ⏳ Breadcrumb navigation (repo > directory > file)
- ⏳ Filter panel as persistent sidebar (currently a card at top of metrics page)

**Implementation Plan:**
1. Add repo selector dropdown to navbar (list all repos, quick switch)
2. Add breadcrumb component (repo > metrics > [filter state])
3. Optionally move filter panel to sidebar layout

**Dependencies:** 04-multi-repo (✅ done), 05-filtering (✅ done)

**Acceptance:** Navigation is intuitive; can drill down and back up.

---

### 7.5 Error handling (display errors gracefully)
**Status:** ✅ **COMPLETED** (basic version)

**What:** Handle and display errors (ingestion failures, metric computation errors, network errors).

**Current Implementation:**
- ✅ Ingestion errors displayed on repo status page (red alert)
- ✅ Failed status badge on repo cards
- ✅ Error message display in repo.html
- ✅ Bootstrap alert components for error display

**Remaining:**
- ⏳ Network error handling (retry button, offline indicator)
- ⏳ "No data for this filter" message when filters yield empty results
- ⏳ Inline form validation for ingestion forms

**Dependencies:** 03-ingestion (✅ done), 02-metric-categories (✅ done)

**Acceptance:** ✅ Errors are displayed clearly; user can recover.

---

### 7.6 Performance (lazy loading, pagination)
**Status:** ⏳ **PARTIALLY COMPLETE**

**What:** Dashboard performs well on large repos (git.git ~60k commits).

**Current Implementation:**
- ✅ DataTables pagination (25 rows per page default)
- ✅ Server-side metric loading (metrics loaded from JSONL file)

**Remaining:**
- ⏳ Lazy loading for large metric sets (load on scroll/demand)
- ⏳ Virtual scrolling for long lists (authors, commits)
- ⏳ Caching filtered results (avoid recomputation)
- ⏳ Loading indicators (spinner/skeleton while data loads)
- ⏳ Server-side pagination for very large tables (10k+ rows)

**Implementation Plan:**
1. Add loading spinners to all data-loading operations
2. Implement server-side pagination for metric tables (if >1000 rows)
3. Add lazy loading for charts (load chart data on tab switch)
4. Implement result caching (cache filtered metrics in memory/session)
5. Test with large repos (cJSON ~1k, Redis ~10k, Git ~60k)

**Dependencies:** 02-metric-categories (✅ done), 05-filtering (✅ done)

**Acceptance:** Dashboard is responsive on large repos; no long freezes.

---

### 7.7 QoL features (export, dark mode, responsive)
**Status:** ⏳ **NOT STARTED**

**What:** Quality-of-life features that improve usability.

**How:**
- Export: download metrics as CSV/JSON (for further analysis)
- Dark mode: toggle between light and dark themes
- Responsive: ✅ already done (Bootstrap 5 responsive)
- Keyboard shortcuts: common actions (e.g., `/` to focus search, `Esc` to clear filters)
- Tooltips: explain metric definitions on hover (e.g., "Churn = added + removed lines")

**Implementation Plan:**
1. Add export buttons (CSV/JSON) to metric tables
2. Add dark mode toggle (Bootstrap dark mode or custom CSS)
3. Add keyboard shortcuts (focus search, clear filters)
4. Add tooltips to metric labels (Bootstrap tooltips)
5. Add help/about page explaining metric definitions

**Dependencies:** 07-dashboard (✅ UI framework done)

**Acceptance:** QoL features work; improve usability.

---

### 7.8 Filtering UI (time, author, path, commit filters)
**Status:** ✅ **COMPLETED**

**What:** UI controls for applying filters to metrics.

**Implementation:**
- ✅ Filter panel card on metrics page with form (date range, author dropdown, path input, commit hashes)
- ✅ Date range inputs (start_date, end_date) parsed as YYYY-MM-DD
- ✅ Author dropdown populated from `distinct_authors()` (respects author merges from 06)
- ✅ Path text input with placeholder examples
- ✅ Commit hashes text input (comma/space-separated)
- ✅ Apply button submits GET form (filters encoded in URL query params)
- ✅ Clear all filters button
- ✅ Active filter badges with individual remove (×) links
- ✅ Click-to-filter funnel icons on file/directory paths and author names in tables
- ✅ "No metrics match" message when filters yield empty results
- ✅ Filters compose with AND logic (backend 05)

**Routes:** `GET /repo/<repo_id>/metrics?start_date=...&end_date=...&author=...&path=...&commits=...`

**Tests:** 11 web tests in test_web.py covering all filter combinations, invalid dates, API parity.

**Dependencies:** 05-filtering (✅ backend done)

**Acceptance:** ✅ Filters can be applied via UI; metrics update accordingly.

---

### 7.9 Author Merging UI (mailmap, manual merge)
**Status:** ✅ **COMPLETED**

**What:** UI for managing author identities and merging duplicates.

**Implementation:**
- ✅ Author management page at `/repo/<repo_id>/authors`
- ✅ Author list with checkboxes for selection
- ✅ Radio buttons to select canonical identity from existing authors
- ✅ Custom canonical name input field
- ✅ Merge button submits selected aliases + canonical
- ✅ Current author groups table showing canonical + merged aliases
- ✅ Un-merge buttons (×) on individual merged aliases
- ✅ "View metrics" link to filter metrics by canonical author
- ✅ Mailmap-aware: `.mailmap` identities shown pre-merged
- ✅ Merges persist per-repo in registry
- ✅ Metrics automatically reflect merged identities

**Routes:**
- `GET /repo/<repo_id>/authors` — author management page
- `POST /repo/<repo_id>/authors/merge` — merge selected authors
- `POST /repo/<repo_id>/authors/unmerge` — undo a single alias merge

**Tests:** 5 tests in test_author_merging.py covering merge, unmerge, validation, persistence, metric updates.

**Dependencies:** 06-author-merging (✅ backend done)

**Acceptance:** ✅ Authors can be merged via UI; metrics reflect canonical identities.

---

## Implementation Notes

- **Tech stack decided:** Flask 3.0+ (backend), Bootstrap 5 + Bootstrap Icons (styling), DataTables (sortable/paginated tables), Chart.js (visualisations — CDN-based, not yet integrated).
- **Incremental build:** Dashboard built incrementally — basic tables (7.1 ✅), filtering UI (7.8 ✅), author merging (7.9 ✅), then visualisations (7.2, 7.3 charts), then polish (7.4-7.7).
- **Rubric focus:** Architecture & UI (25%) + Usability (25%) = 50% of grade. Invest in visualisation quality and navigation.
- **Performance:** Lazy loading and pagination are essential for large repos (Usability tier: "good performance on large (~100,000 commits) repos").
- **Testing:** 53 tests passing (11 web route tests, 5 author merging tests, 8 filtering tests, 8 ingestion tests, 8 metric engine tests, plus additional integration tests).
- **Filter state in URL:** Filters are encoded as GET query params, so filtered views are shareable/bookmarkable (partial 7.4 URL state).

---

## Acceptance Criteria

- [x] Dashboard layout is clean and functional (✅ minimal version done)
- [x] Metric tables display data with sorting and pagination (✅ DataTables done)
- [ ] Metric visualisations (charts, treemaps) work and are interactive
- [ ] Author visualisations (contribution charts, ownership pies) work
- [ ] Navigation is intuitive (repo selector, filters, breadcrumb)
- [x] Errors are displayed clearly; user can recover (✅ basic version done)
- [ ] Dashboard is responsive on large repos (no long freezes)
- [ ] QoL features work (export, dark mode, tooltips)
- [x] Filtering UI works (time, author, path, commit filters) (✅ done)
- [x] Author merging UI works (mailmap, manual merge) (✅ done)

---

## Build Priority (Updated)

1. **7.2 Metric visualisation** — High rubric impact (Architecture & UI 25%), biggest remaining gap
2. **7.3 Author visualisation** — High value, author data already available
3. **7.4 Navigation** — Polish, improve UX (repo selector, breadcrumbs)
4. **7.6 Performance** — Test with large repos, optimize
5. **7.7 QoL features** — Polish, nice-to-have (export, dark mode, tooltips)
