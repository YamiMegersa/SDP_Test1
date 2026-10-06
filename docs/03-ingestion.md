# 03 — Ingestion (Zip + Clone URL)

> **Purpose:** Accept repositories in two forms (zip upload or remote URL), extract/clone them,
> verify the `.git` directory, and trigger the metric engine (01).
>
> **Rubric basis:** "Both: zip file and remote URL ingestion" gates the ≤50% Requirements band.
>
> **Complexity:** Low. Plumbing work — a few hours each.

## Sub-tasks

### 3.1 Zip upload
**What:** Accept a zip file of the repo containing `.git`, extract it, verify `.git` exists.

**How:**
- Receive zip file via upload endpoint
- Extract to temporary directory
- Verify `.git/HEAD` exists (confirms it's a git repo)
- Assign a `repo_id` and register in the repo registry (04)
- Trigger metric engine (01) on the extracted repo

**Gotchas:**
- Zip may contain a top-level directory (e.g., `repo-name/.git`) — handle both cases
- Large zips (git.git ~300MB+): stream extraction, don't buffer in memory
- Invalid zips: handle gracefully, return error

**Dependencies:** 04-multi-repo (repo registry — but can be stubbed initially)

**Acceptance:** Upload a valid zip, repo is registered and metric engine starts.

---

### 3.2 URL clone
**What:** Accept a remote repository URL, deeply clone it (full history required for metrics).

**How:**
- Receive URL via upload endpoint
- Run `git clone --mirror <url> <repo_dir>` or `git clone --bare <url> <repo_dir>`
  - `--mirror` clones all refs (branches, tags) — preferred for completeness
  - `--bare` clones without working tree — sufficient for metrics
- Verify `.git/HEAD` exists (or `HEAD` in bare repo)
- Assign a `repo_id` and register in the repo registry (04)
- Trigger metric engine (01) on the cloned repo

**Gotchas:**
- Large repos (git.git ~300MB+): clone can take minutes; run asynchronously
- Network errors: handle gracefully, retry logic?
- Invalid URLs: validate format, return error
- Authentication: private repos? (brief doesn't mention; assume public only)

**Dependencies:** 04-multi-repo (repo registry — but can be stubbed initially)

**Acceptance:** Provide a valid URL, repo is cloned, registered, and metric engine starts.

---

### 3.3 Repo registration
**What:** Assign `repo_id`, store metadata (name, source, ingestion timestamp, commit count).

**How:**
- Generate unique `repo_id` (UUID or auto-increment)
- Store metadata:
  - `repo_id`
  - `name` (user-provided or derived from URL/zip filename)
  - `source_type` (zip or url)
  - `source_path` (local path to extracted/cloned repo)
  - `ingested_at` (timestamp)
  - `commit_count` (after 01 completes)
  - `status` (ingesting, ready, failed)
- Storage: database table or JSON file

**Dependencies:** None (but 04-multi-repo will extend this)

**Acceptance:** After ingestion, repo metadata is stored and queryable.

---

### 3.4 Ingestion pipeline
**What:** Orchestrate the ingestion flow: receive → extract/clone → verify → register → trigger 01.

**How:**
- Synchronous for small repos (cJSON ~1k commits): upload → extract → register → run 01 → return
- Asynchronous for large repos (git.git ~60k commits): upload → extract → register → queue 01 → poll status
- Status endpoint: check ingestion progress (queued, running, completed, failed)
- Error handling: if 01 fails, mark repo as failed, store error message

**Dependencies:** 01-metric-engine, 3.1, 3.2, 3.3

**Acceptance:** Ingestion pipeline works end-to-end for test repos.

---

### 3.5 Error handling
**What:** Handle invalid inputs, missing `.git`, clone failures, network errors.

**How:**
- Validate zip: must be a valid zip file, must contain `.git/HEAD`
- Validate URL: must be a valid git URL format
- Clone failures: capture error message, mark repo as failed
- Network errors: retry logic? (brief doesn't specify; keep it simple)
- User-facing errors: return clear error messages (not stack traces)

**Dependencies:** 3.1, 3.2

**Acceptance:** Invalid inputs return clear error messages; failed ingestions are marked as failed.

---

## Implementation Notes

- **Implemented:** Framework-agnostic Python ingestion service (`rat_metric_engine.ingestion`) that a web endpoint or CLI can call.
- **Async ingestion:** Optional background-thread mode with pollable registry status for long-running jobs.
- **Storage location:** Extracted/cloned repos are stored under a configurable registry base directory (`repos/<repo_id>/`), with metrics under `metrics/<repo_id>/`.
- **Cleanup:** Failed ingestions clean up extracted/cloned repository files while preserving failed registry metadata.
- **Security:** Zip extraction rejects unsafe member paths; URL cloning uses argument-list subprocess calls and URL validation.

---

## Acceptance Criteria

- [x] Zip upload works for small repos (fixture repo with top-level directory in zip)
- [x] URL clone works for small repos (local git repo cloned via `git clone --mirror`)
- [x] Invalid zip returns clear error
- [x] Invalid URL returns clear error
- [x] Repo metadata is stored after ingestion in a JSON registry
- [x] Metric engine (01) is triggered automatically after ingestion and writes object metrics JSONL
- [x] Ingestion status is queryable, including async background-thread ingestion
- [x] Failed ingestions are marked as failed with error message
