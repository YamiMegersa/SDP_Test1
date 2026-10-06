# 04 — Multi-Repository Support

> **Purpose:** Support multiple repositories in the dashboard, with a repo registry, per-repo
> data isolation, and a UI selector.
>
> **Rubric basis:** Tier-3 feature (75%/100% band of Requirements). Cheapest tier-3 if designed-in.
>
> **Complexity:** Low-Moderate. ~free if schema is multi-repo from the start.

## Sub-tasks

### 4.1 Data model (repo_id, metadata, per-repo namespace)
**What:** Design schema so all metric data is scoped by `repo_id`.

**How:**
- `repos` table: `(repo_id, name, source_type, source_path, ingested_at, commit_count, status)`
- All metric tables include `repo_id` as foreign key:
  - `commits(repo_id, commit_hash, parent_hash, committer_date, author_email, author_name)`
  - `file_deltas(repo_id, commit_hash, file_path, l_plus, l_minus)`
  - `directory_metrics(repo_id, commit_hash, dir_path, l_plus, l_minus, delta, churn)`
  - etc.
- Indexes: `(repo_id, commit_hash)`, `(repo_id, file_path)`, `(repo_id, dir_path)`

**Dependencies:** None (design decision)

**Acceptance:** Schema supports multiple repos with data isolation.

---

### 4.2 Repo registry (list/add/delete repos)
**What:** API endpoints to list, add, and delete repositories.

**How:**
- `GET /api/repos` — list all repos with metadata
- `POST /api/repos` — add a repo (triggers ingestion, 03)
- `DELETE /api/repos/<repo_id>` — delete a repo and its data
- `GET /api/repos/<repo_id>` — get repo details

**Dependencies:** 03-ingestion (for adding repos)

**Acceptance:** Can list, add, and delete repos via API.

---

### 4.3 UI (repo selector, per-repo dashboard)
**What:** Dashboard UI to switch between repos, showing per-repo metrics.

**How:**
- Repo selector: dropdown in top nav or sidebar
- Per-repo dashboard: when a repo is selected, show its metrics (file/dir/repo/set/author)
- Breadcrumb: show current repo name in page title/header
- Empty state: when no repos exist, show "Upload a repository" prompt

**Dependencies:** 07-dashboard (UI framework)

**Acceptance:** Can switch between repos in the UI; metrics are scoped to selected repo.

---

### 4.4 Concurrent ingestion (handle multiple repos)
**What:** Support multiple repos being ingested simultaneously.

**How:**
- Async ingestion (03.4): each repo ingestion runs in background
- Status polling: frontend polls `/api/repos/<repo_id>/status` for progress
- Concurrency limits: limit simultaneous ingestions to avoid resource exhaustion (e.g., max 2 at a time)
- Queue: if limit reached, queue additional ingestions

**Dependencies:** 03.4 (async ingestion pipeline)

**Acceptance:** Can ingest multiple repos concurrently; status is queryable.

---

## Implementation Notes

- **Design-in from day 1:** Even if the UI comes later (07), the schema must support multi-repo from the start. Retrofitting is painful.
- **Data isolation:** All queries must include `repo_id` filter to prevent cross-repo data leakage.
- **Cleanup:** Deleting a repo should clean up extracted/cloned files and metric data.
- **Performance:** Indexes on `(repo_id, ...)` are essential for query performance.

---

## Acceptance Criteria

- [ ] Schema includes `repo_id` in all metric tables
- [ ] Can list repos via API
- [ ] Can add a repo (triggers ingestion)
- [ ] Can delete a repo (cleans up data)
- [ ] UI shows repo selector (dropdown)
- [ ] Metrics are scoped to selected repo
- [ ] Can ingest multiple repos concurrently
- [ ] Ingestion status is queryable per repo
