# 07 — Dashboard UI

> **Purpose:** Web-app dashboard for viewing metrics, with visualisations, navigation, and QoL
> features. Cross-cutting: can be built incrementally alongside other features.
>
> **Rubric basis:** Architecture & UI Design (25% weight) + Usability (25% weight) = 50% of grade.
> "Inspired visualisation" and "excellent navigation" at 100% tier.
>
> **Complexity:** High. UI/UX work is inherently iterative; visualisation quality is subjective.

## Sub-tasks

### 7.1 Dashboard layout (multi-repo views, metric tables)
**What:** Overall page structure: repo selector, metric tables, filter panel.

**How:**
- Layout: header (repo selector, navigation), sidebar (filters), main content (metric tables/visualisations)
- Responsive: works on desktop and tablet (mobile optional)
- Metric tables: sortable columns, pagination for large result sets
- Empty state: "Upload a repository" prompt when no repos exist

**Dependencies:** 04-multi-repo (repo selector), 05-filtering (filter panel)

**Acceptance:** Dashboard layout is clean and functional; metric tables display data.

---

### 7.2 Metric visualisation (charts, heatmaps, treemaps)
**What:** Visual representations of metrics for quick insight.

**How:**
- File/dir metrics: bar charts (top files by churn), treemaps (directory structure sized by churn)
- Commit set metrics: time series (churn over time), line charts (growth trend)
- Repository metrics: summary cards (total churn, total files, total authors)
- Visualisation library: D3, Chart.js, or similar (TBD based on tech stack)
- Interactive: hover for details, click to drill down

**Dependencies:** 02-metric-categories (metric data), 05-filtering (filtered data)

**Acceptance:** Metrics are visualised clearly; charts are interactive.

---

### 7.3 Author visualisation (contribution charts, ownership pies)
**What:** Visual representations of author metrics.

**How:**
- Author contribution: bar chart (churn by author), pie chart (ownership %)
- Author timeline: stacked area chart (churn over time by author)
- Author list: table with metrics (modifications, churn, ownership), sortable
- Click author: filter dashboard to that author (05.2)

**Dependencies:** 02.5 (author metrics), 06-author-merging (canonical identities)

**Acceptance:** Author metrics are visualised clearly; can filter by author.

---

### 7.4 Navigation (repo selector, filter panel, breadcrumb)
**What:** Intuitive navigation between repos, filters, and metric views.

**How:**
- Repo selector: dropdown in header (04.3)
- Filter panel: sidebar with filter controls (05.7)
- Breadcrumb: show current location (repo > directory > file)
- Back button: navigate up the breadcrumb
- URL state: navigation state in URL (for sharing/bookmarking)

**Dependencies:** 04-multi-repo, 05-filtering

**Acceptance:** Navigation is intuitive; can drill down and back up.

---

### 7.5 Error handling (display errors gracefully)
**What:** Handle and display errors (ingestion failures, metric computation errors, network errors).

**How:**
- Error boundaries: catch errors in UI components, display friendly message
- Ingestion errors: show in repo status (03.5)
- Metric errors: show in metric table/visualisation (e.g., "No data for this filter")
- Network errors: retry button, offline indicator
- Validation errors: inline form validation (e.g., invalid URL format)

**Dependencies:** 03-ingestion (ingestion errors), 02-metric-categories (metric errors)

**Acceptance:** Errors are displayed clearly; user can recover (retry, clear filters, etc.).

---

### 7.6 Performance (lazy loading, pagination)
**What:** Dashboard performs well on large repos (git.git ~60k commits).

**How:**
- Lazy loading: load metric data on demand (not all at once)
- Pagination: for large tables (files, commits), show 50/100 per page
- Virtual scrolling: for long lists (commits, authors), render only visible rows
- Caching: cache filtered metric results (if same filter is applied again)
- Loading indicators: show spinner/skeleton while data loads

**Dependencies:** 02-metric-categories (metric data), 05-filtering (filtered data)

**Acceptance:** Dashboard is responsive on large repos; no long freezes.

---

### 7.7 QoL features (export, dark mode, responsive)
**What:** Quality-of-life features that improve usability.

**How:**
- Export: download metrics as CSV/JSON (for further analysis)
- Dark mode: toggle between light and dark themes
- Responsive: works on different screen sizes (desktop, tablet, mobile)
- Keyboard shortcuts: common actions (e.g., `/` to focus search, `Esc` to clear filters)
- Tooltips: explain metric definitions on hover (e.g., "Churn = added + removed lines")

**Dependencies:** 07-dashboard (UI framework)

**Acceptance:** QoL features work; improve usability.

---

## Implementation Notes

- **Tech stack TBD:** Frontend framework (React/Vue/Svelte) and visualisation library (D3/Chart.js) are TBD.
- **Incremental build:** Dashboard can be built incrementally — start with basic tables (7.1), add visualisations (7.2, 7.3), then polish (7.4-7.7).
- **Rubric focus:** Architecture & UI (25%) + Usability (25%) = 50% of grade. Invest in visualisation quality and navigation.
- **Performance:** Lazy loading and pagination are essential for large repos (Usability tier: "good performance on large (~100,000 commits) repos").

---

## Acceptance Criteria

- [ ] Dashboard layout is clean and functional
- [ ] Metric tables display data with sorting and pagination
- [ ] Metric visualisations (charts, treemaps) work and are interactive
- [ ] Author visualisations (contribution charts, ownership pies) work
- [ ] Navigation is intuitive (repo selector, filters, breadcrumb)
- [ ] Errors are displayed clearly; user can recover
- [ ] Dashboard is responsive on large repos (no long freezes)
- [ ] QoL features work (export, dark mode, tooltips)
