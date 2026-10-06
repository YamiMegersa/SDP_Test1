# 06 — Author Merging

> **Purpose:** Merge multiple author identities (emails/names) into canonical identities, via
> `.mailmap` parsing and manual merge UI.
>
> **Rubric basis:** Tier-3 feature (75%/100% band of Requirements). Mailmap part is cheap; manual
> merge UI is the expensive part.
>
> **Complexity:** Moderate-High. Mailmap parsing is straightforward; manual merge UI + re-aggregation
> semantics are genuinely costly.

## Sub-tasks

### 6.1 Mailmap parsing
**What:** Read `.mailmap` file from repo, parse format, build alias map.

**How:**
- Mailmap format (git standard):
  - `Canonical Name <canonical@email>` — map all commits with this email to canonical
  - `Canonical Name <canonical@email> <commit@email>` — map specific commit email to canonical
  - `Canonical Name <canonical@email> Commit Name <commit@email>` — map specific name+email
- Parse at ingestion time (03), store as alias map: `{commit_email: canonical_email, ...}`
- Apply alias map to commit author metadata (01.1)

**Dependencies:** 03-ingestion (access to repo files), 01.1 (commit author metadata)

**Acceptance:** Mailmap is parsed; commit authors are mapped to canonical identities.

---

### 6.2 Identity resolution
**What:** Map commit author emails/names to canonical identities using mailmap.

**How:**
- After mailmap parsing (6.1), apply alias map to all commits:
  - `canonical_email = alias_map.get(commit_email, commit_email)`
  - `canonical_name = alias_map.get(commit_email, commit_name)` (if mailmap specifies name)
- Store canonical identity per commit: `(author_id, canonical_email, canonical_name)`
- Build distinct author list: `SELECT DISTINCT author_id FROM commits WHERE repo_id = ?`

**Dependencies:** 6.1 (mailmap parsing)

**Acceptance:** All commits have canonical author identities; distinct author list is correct.

---

### 6.3 Manual merge UI
**What:** UI to select multiple identities, merge them into one canonical identity.

**How:**
- UI: author list with checkboxes, "Merge selected" button
- User selects multiple authors, picks one as canonical (or enters new canonical name/email)
- Backend: create merge mapping `{alias_author_id: canonical_author_id}`
- Apply mapping to author metrics (02.5) — recompute author-scoped aggregates
- UI feedback: show merged authors as a group, allow un-merging (6.6)

**Dependencies:** 02.5 (author metrics), 07-dashboard (UI framework)

**Acceptance:** Can select multiple authors, merge them, and see updated author metrics.

---

### 6.4 Merge persistence
**What:** Store merge mappings so they persist across sessions.

**How:**
- `author_merges` table: `(repo_id, alias_author_id, canonical_author_id, merged_at)`
- On load: apply merge mappings to author identity resolution (6.2)
- Merge mappings are repo-scoped (different repos may have different merges)

**Dependencies:** 6.3 (manual merge UI)

**Acceptance:** Merge mappings persist across sessions; author metrics reflect merges on reload.

---

### 6.5 Re-aggregation
**What:** Apply merge mappings to author metrics (recompute author-scoped aggregates).

**How:**
- When a merge happens, recompute author metrics (02.5) for affected authors:
  - `n_{H,o,canonical} += n_{H,o,alias}` (sum modifications)
  - `λ_{H,o,canonical} += λ_{H,o,alias}` (sum churn)
  - `ω_{H,o,canonical} = λ_{H,o,canonical} / λ_{H,o}` (recompute ownership)
- Alternatively: apply alias map at query time (cheaper, no recomputation)
  - `WHERE author_id IN (canonical_id, alias_id1, alias_id2, ...)`
- Recommendation: apply at query time for flexibility; precompute if performance is an issue.

**Dependencies:** 6.4 (merge persistence), 02.5 (author metrics)

**Acceptance:** After merge, author metrics are correct (sum of merged identities).

---

### 6.6 Un-merge
**What:** Ability to undo a manual merge.

**How:**
- UI: "Un-merge" button on merged author group
- Backend: delete merge mapping from `author_merges` table
- Re-aggregate: recompute author metrics for un-merged authors (or apply updated alias map at query time)
- UI feedback: show authors as separate again

**Dependencies:** 6.4 (merge persistence), 6.5 (re-aggregation)

**Acceptance:** Can un-merge authors; metrics revert to pre-merge state.

---

## Implementation Notes

- **Design decision:** Store raw per-identity data, apply alias map at aggregation layer (so merge is cheap). This avoids recomputing the entire metric engine (01) when merges change.
- **Mailmap vs manual:** Mailmap is repo-provided (automatic); manual merge is user-driven (UI). Both produce the same alias map.
- **Merge scope:** Merges are repo-scoped (different repos may have different merges for the same person).
- **Performance:** For large repos, applying alias map at query time is cheaper than recomputing aggregates.

---

## Acceptance Criteria

- [x] Mailmap is parsed correctly (all formats)
- [x] Commit authors are mapped to canonical identities
- [x] Distinct author list reflects canonical identities
- [x] Manual merge UI works (select authors, merge)
- [x] Merge mappings persist across sessions
- [x] Author metrics are correct after merge (sum of merged identities)
- [x] Can un-merge authors; metrics revert correctly
