# 01 — Metric Engine (Base Extraction)

> **Purpose:** Walk git history, extract per-commit per-file `l⁺`/`l⁻` deltas with rename detection,
> binary filtering, and deletion handling. This is the foundation for all metric categories.
>
> **Rubric basis:** Metric correctness (50% weight), efficient computation (Architecture 25%),
> performance at scale (Usability 25%).
>
> **Complexity:** High (critical path). Everything else depends on this.

## Sub-tasks

### 1.1 Git history traversal
**What:** Walk non-merge commits reachable from `h_r` (typically HEAD), in topological order, with `h[p]` linkage.

**How:**
- `git log --no-merges --format="%H %P %ct" <ref>` — outputs commit hash, parent hash(es), committer timestamp
- For each commit, store `(hash, parent_hash, committer_date)`
- Topological order: git log outputs in reverse chronological order; for metric computation, process in forward order (oldest first) so `h[p]` is always processed before `h`

**Gotchas:**
- Initial commit has no parent (`h[p] = h_∅`)
- Merge commits have multiple parents; exclude them (`--no-merges`)
- Large repos (git.git ~60k commits): stream output, don't load all into memory

**Dependencies:** None

**Acceptance:** For a test repo, output list of `(commit_hash, parent_hash, committer_date)` for all non-merge commits in forward order.

---

### 1.2 Per-commit diff extraction
**What:** For each commit `h`, compute `l⁺_{h,f}` and `l⁻_{h,f}` for each file `f`.

**How:**
- `git diff-tree -r -M50 --numstat <parent_hash> <commit_hash>` — outputs per-file added/removed lines with rename detection
- For initial commit: `git diff-tree -r -M50 --numstat --root <commit_hash>`
- Parse numstat output: `<added>\t<removed>\t<path>` (binary files show `-` for added/removed)

**Gotchas:**
- Rename detection: git may output `old_path => new_path` for renames; parse accordingly
- Binary files: skip (numstat shows `-`)
- Large diffs: stream output, don't buffer

**Dependencies:** 1.1 (need commit list with parent hashes)

**Acceptance:** For a test commit, output list of `(file_path, l_plus, l_minus)` with correct rename handling.

---

### 1.3 Binary file detection
**What:** Skip binary files (not measured per brief).

**How:**
- git diff-tree --numstat shows `-` for added/removed on binary files
- Filter out lines where added or removed is `-`

**Dependencies:** 1.2

**Acceptance:** Binary files (images, executables) are excluded from output.

---

### 1.4 Deletion handling
**What:** When `f ∈ h[p][F]` but `f ∉ h[F]`, record `l_{h,f} = lines in f at h[p]`, `l⁺_{h,f} = 0`.

**How:**
- git diff-tree --numstat already handles deletions: shows `<0>\t<removed>\t<path>` for deleted files
- No special handling needed; numstat output is correct

**Dependencies:** 1.2

**Acceptance:** Deleted files show `l⁺=0`, `l⁻=lines_removed`.

---

### 1.5 Rename handling
**What:** When git detects rename (similarity ≥ 50%), attribute changes to new path; pure rename has `l⁺=l=0`.

**How:**
- git diff-tree -M50 outputs renames as `old_path => new_path` with `l⁺`/`l⁻` for the changes
- Parse the `=>` syntax; use `new_path` as the file identifier
- Pure rename: `l⁺=0`, `l⁻=0` (no changes, just rename)

**Dependencies:** 1.2

**Acceptance:** Renamed file shows metrics under new path; pure rename has `l⁺=l⁻=0`.

---

### 1.6 Initial commit handling
**What:** `h_∅` is empty, so first commit's `l⁺` = all lines, `l⁻` = 0.

**How:**
- Use `--root` flag with git diff-tree for the initial commit
- Output shows all files as added (`l⁺` = file line count, `l⁻` = 0)

**Dependencies:** 1.2

**Acceptance:** Initial commit shows all files as added with correct line counts.

---

### 1.7 Data model for per-commit per-file deltas
**What:** Store `(commit_hash, file_path, l_plus, l_minus)` for all commits.

**How:**
- Output format: TSV or JSON stream
- Schema: `(repo_id, commit_hash, file_path, l_plus, l_minus)`
- Storage: write to file or database as stream (don't buffer all in memory)

**Dependencies:** 1.1, 1.2

**Acceptance:** For a test repo, output file contains all `(commit, file, l⁺, l⁻)` tuples.

---

### 1.8 Performance: single pass, streaming, no full diffs
**What:** Process history in one pass, stream output, avoid loading full diffs into memory.

**How:**
- Pipe git log output to git diff-tree in a loop
- Write output to file/DB as stream
- For large repos (git.git ~60k commits): expect ~minutes, not hours

**Dependencies:** 1.1, 1.2, 1.7

**Acceptance:** Ingestion of git.git completes in reasonable time (< 10 minutes?).

---

## Implementation Notes

- **Tech stack TBD:** This plan is tech-agnostic. Implementation will use git CLI commands; the wrapper language (Python/Node/Go) is TBD.
- **Rename detection threshold:** -M50% per brief. Git's default is 50%, so `-M50` or just `-M` works.
- **Binary detection:** git's own detection via numstat `-` output.
- **Initial commit:** `--root` flag is essential.
- **Streaming:** For large repos, don't buffer all commits in memory; process and write as you go.

---

## Acceptance Criteria

- [ ] For cJSON (~1k commits), output file contains all `(commit, file, l⁺, l⁻)` tuples
- [ ] Renamed files show metrics under new path
- [ ] Pure renames have `l⁺=l⁻=0`
- [ ] Deleted files show `l=0`, `l⁻=lines_removed`
- [ ] Binary files are excluded
- [ ] Initial commit shows all files as added
- [ ] Performance: cJSON ingests in < 1 minute
