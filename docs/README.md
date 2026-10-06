# RAT Implementation Plan

> This directory contains the implementation plan for the Repo Analysis Tool (RAT).
> Each feature is broken down into a separate markdown file with sub-tasks, implementation
> approach, dependencies, and acceptance criteria.

## Dependency Graph

```
01-metric-engine (base extraction: history walk, rename, binary, deletions, l⁺/l⁻)
    ↓
02-metric-categories (aggregation layers: file/dir/repo/set/author metrics)
    ↓
03-ingestion (zip + URL clone) → triggers 01 + 02
    ↓
04-multi-repo (repo registry, schema, UI selector)
    ↓
05-filtering (time, author, path, commits, manual list)
    ↓
06-author-merging (mailmap + manual merge UI)
    ↓
07-dashboard (UI, visualisation, navigation) — cross-cutting, can be built incrementally
    ↓
08-validation (test repos, sample metrics, benchmarking)
```

## Build Order

1. **01-metric-engine** — foundation; everything else depends on this
2. **02-metric-categories** — aggregation on top of engine output (marginal cost ≈ 0 after 01)
3. **03-ingestion** — needed to load repos for metrics; triggers 01 + 02
4. **04-multi-repo** — schema design from day 1; UI can come later
5. **05-filtering** — makes metrics demonstrable; feeds Usability criterion
6. **06-author-merging** — tier-3 feature; mailmap first, manual UI last
7. **07-dashboard** — cross-cutting; can be built incrementally alongside other features
8. **08-validation** — last; needs all other features to be functional

## File List

| File | Feature | Complexity | Priority |
|------|---------|------------|----------|
| [01-metric-engine.md](01-metric-engine.md) | Base extraction (history walk, rename, binary, deletions, l⁺/l⁻) | High | 1 |
| [02-metric-categories.md](02-metric-categories.md) | Aggregation layers (file/dir/repo/set/author metrics) | Low (after 01) | 2 |
| [03-ingestion.md](03-ingestion.md) | Zip upload + URL clone | Low | 3 |
| [04-multi-repo.md](04-multi-repo.md) | Multi-repo support | Low-Moderate | 4 |
| [05-filtering.md](05-filtering.md) | Filtering dimensions | Moderate | 5 |
| [06-author-merging.md](06-author-merging.md) | Author merging | Moderate-High | 6 |
| [07-dashboard.md](07-dashboard.md) | Dashboard UI | High | 7 (cross-cutting) |
| [08-validation.md](08-validation.md) | Validation harness | Moderate | 8 |

## Notes

- **Tech stack TBD** — these plans are tech-agnostic. Implementation will use git CLI commands; the wrapper language/framework is TBD (see PROJECT_STRUCTURE.md §8).
- **Metric engine (01) is the critical path** — all other features depend on it.
- **Metric categories (02) are pure aggregation** once the engine exists — marginal cost ≈ 0.
- **Tier-3 features (04, 05, 06) are the intended flex room** per the rubric (§5.5 of PROJECT_STRUCTURE.md).
- **Dashboard (07) is cross-cutting** and can be built incrementally alongside other features.
- **Validation (08) is last** — it needs all other features to be functional.

## Work Strategy

- Work through features in build order (01 → 08).
- Within each feature, work through sub-tasks in order (dependencies are noted).
- Acceptance criteria at the end of each file define "done" for that feature.
- If time pressure arises, follow the abandonment order in PROJECT_STRUCTURE.md §5.5.
