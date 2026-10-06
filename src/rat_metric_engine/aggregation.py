"""Aggregation layers for RAT metric categories.

This module builds file, directory, repository, commit-set, and author metrics
from the base per-commit per-file deltas emitted by :mod:`rat_metric_engine.engine`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Iterator, Literal

from .engine import CommitInfo, FileDelta

ObjectType = Literal["file", "directory", "repository"]
ROOT_PATH = "."


@dataclass(frozen=True)
class ObjectMetric:
    """Added/removed/growth/churn for one object in one commit."""

    repo_id: str
    commit_hash: str
    committer_date: int
    object_path: str
    object_type: ObjectType
    l_plus: int
    l_minus: int
    author_name: str = ""
    author_email: str = ""

    @property
    def growth(self) -> int:
        """Net line growth: ``l_plus - l_minus``."""

        return self.l_plus - self.l_minus

    @property
    def churn(self) -> int:
        """Changed lines: ``l_plus + l_minus``."""

        return self.l_plus + self.l_minus

    @property
    def author_identity(self) -> str:
        """Stable display identity for the commit author."""

        if self.author_email and self.author_name:
            return f"{self.author_name} <{self.author_email}>"
        return self.author_name or self.author_email


@dataclass(frozen=True)
class CommitSetMetric:
    """Aggregated metrics for one object over a commit set H."""

    repo_id: str
    object_path: str
    object_type: ObjectType
    commit_count: int
    l_plus: int
    l_minus: int
    modifications: int

    @property
    def growth(self) -> int:
        """Net line growth over the commit set."""

        return self.l_plus - self.l_minus

    @property
    def churn(self) -> int:
        """Changed lines over the commit set."""

        return self.l_plus + self.l_minus

    @property
    def modification_frequency(self) -> float:
        """Modifications divided by ``|H|``."""

        if self.commit_count == 0:
            return 0.0
        return self.modifications / self.commit_count

    @property
    def churn_rate(self) -> float:
        """Churn divided by ``|H|``."""

        if self.commit_count == 0:
            return 0.0
        return self.churn / self.commit_count


@dataclass(frozen=True)
class AuthorMetric:
    """Per-author contribution metrics for one object over a commit set H."""

    repo_id: str
    object_path: str
    object_type: ObjectType
    author: str
    commit_count: int
    total_churn: int
    modifications: int
    author_churn: int

    @property
    def ownership(self) -> float:
        """Author churn divided by total object churn over ``H``."""

        if self.total_churn == 0:
            return 0.0
        return self.author_churn / self.total_churn


def file_metric_from_delta(delta: FileDelta, commit: CommitInfo | None = None) -> ObjectMetric:
    """Convert a base file delta into a per-commit file metric."""

    return ObjectMetric(
        repo_id=delta.repo_id,
        commit_hash=delta.commit_hash,
        committer_date=delta.committer_date,
        object_path=delta.file_path,
        object_type="file",
        l_plus=delta.l_plus,
        l_minus=delta.l_minus,
        author_name=commit.author_name if commit else "",
        author_email=commit.author_email if commit else "",
    )


def iter_file_metrics(deltas: Iterable[FileDelta]) -> Iterator[ObjectMetric]:
    """Yield file metrics derived directly from base deltas."""

    for delta in deltas:
        yield file_metric_from_delta(delta)


def parent_directories(path: str) -> tuple[str, ...]:
    """Return all directory ancestors of a file path, including the root."""

    parts = [part for part in path.split("/") if part]
    if len(parts) <= 1:
        return (ROOT_PATH,)

    directories = [ROOT_PATH]
    current: list[str] = []
    for part in parts[:-1]:
        current.append(part)
        directories.append("/".join(current))
    return tuple(directories)


def build_commit_object_metrics(file_metrics: Iterable[ObjectMetric]) -> list[ObjectMetric]:
    """Build file, directory, and repository metrics for a single commit.

    Directory and repository values are recursive rollups over file metrics for
    the commit. The root directory is represented by ``ROOT_PATH`` and emitted as
    a repository metric, because repository metrics are the root rollup.
    """

    files = list(file_metrics)
    if not files:
        return []

    directory_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for metric in files:
        for directory in parent_directories(metric.object_path):
            totals = directory_totals[directory]
            totals[0] += metric.l_plus
            totals[1] += metric.l_minus

    first = files[0]
    object_metrics = list(files)
    for directory in sorted(path for path in directory_totals if path != ROOT_PATH):
        l_plus, l_minus = directory_totals[directory]
        object_metrics.append(
            ObjectMetric(
                repo_id=first.repo_id,
                commit_hash=first.commit_hash,
                committer_date=first.committer_date,
                object_path=directory,
                object_type="directory",
                l_plus=l_plus,
                l_minus=l_minus,
                author_name=first.author_name,
                author_email=first.author_email,
            )
        )

    root_l_plus, root_l_minus = directory_totals[ROOT_PATH]
    object_metrics.append(
        ObjectMetric(
            repo_id=first.repo_id,
            commit_hash=first.commit_hash,
            committer_date=first.committer_date,
            object_path=ROOT_PATH,
            object_type="repository",
            l_plus=root_l_plus,
            l_minus=root_l_minus,
            author_name=first.author_name,
            author_email=first.author_email,
        )
    )
    return object_metrics


def iter_commit_object_metrics(file_metrics: Iterable[ObjectMetric]) -> Iterator[ObjectMetric]:
    """Yield file, directory, and repository metrics grouped by commit."""

    grouped: dict[tuple[str, str], list[ObjectMetric]] = defaultdict(list)
    for metric in file_metrics:
        grouped[(metric.repo_id, metric.commit_hash)].append(metric)

    for (_repo_id, _commit_hash), metrics in grouped.items():
        yield from build_commit_object_metrics(metrics)


def _normalize_path_filter(path: str | None) -> str | None:
    """Normalize a file/directory path filter.

    Returns ``None`` when no real filtering is requested (unset, empty, or the
    root path), otherwise a slash-stripped path used for exact/prefix matching.
    """

    if not path:
        return None
    normalized = path.strip().strip("/")
    if not normalized or normalized == ROOT_PATH:
        return None
    return normalized


def _path_matches(object_path: str, filter_path: str) -> bool:
    """Return True if ``object_path`` is the path or lives under it.

    Matches the brief's exact-match (files) and prefix-match (directories)
    semantics from docs/05-filtering.md §5.3.
    """

    return object_path == filter_path or object_path.startswith(f"{filter_path}/")


def _commit_set_filters(
    metric: ObjectMetric,
    selected_hashes: set[str] | None,
    start_time: int | None,
    end_time: int | None,
    author: str | None,
) -> bool:
    """Return True if a metric's *commit* (time/author/hash) passes the filters.

    Deliberately excludes the path filter: path only narrows which objects are
    reported, it must never shrink the commit set size ``|H|`` used for
    modification frequency / churn rate denominators.
    """

    if selected_hashes is not None and metric.commit_hash not in selected_hashes:
        return False
    if start_time is not None and metric.committer_date < start_time:
        return False
    if end_time is not None and metric.committer_date >= end_time:
        return False
    if author is not None and metric.author_identity != author:
        return False
    return True


def aggregate_commit_set(
    metrics: Iterable[ObjectMetric],
    commit_hashes: Iterable[str] | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    author: str | None = None,
    path: str | None = None,
) -> list[CommitSetMetric]:
    """Aggregate object metrics over a commit set H.

    ``commit_hashes`` can be used for a manual commit list (or a specific
    commit/hash range already resolved to hashes). ``start_time`` is inclusive
    and ``end_time`` is exclusive, matching the project formula for a
    time-bounded commit set. ``author`` restricts H to commits by that author
    (post-merge identity). ``path`` restricts the *reported objects* to an
    exact file path or anything under a directory path, without affecting the
    size of H.
    """

    selected_hashes = set(commit_hashes) if commit_hashes is not None else None
    normalized_path = _normalize_path_filter(path)
    selected_commits: set[str] = set()
    totals: dict[tuple[str, str, ObjectType], list[int]] = defaultdict(lambda: [0, 0, 0])
    for metric in metrics:
        if not _commit_set_filters(metric, selected_hashes, start_time, end_time, author):
            continue
        selected_commits.add(metric.commit_hash)
        if normalized_path is not None and not _path_matches(metric.object_path, normalized_path):
            continue
        key = (metric.repo_id, metric.object_path, metric.object_type)
        totals[key][0] += metric.l_plus
        totals[key][1] += metric.l_minus
        if metric.churn > 0:
            totals[key][2] += 1

    commit_count = len(selected_hashes) if selected_hashes is not None else len(selected_commits)

    return [
        CommitSetMetric(
            repo_id=repo_id,
            object_path=object_path,
            object_type=object_type,
            commit_count=commit_count,
            l_plus=l_plus,
            l_minus=l_minus,
            modifications=modifications,
        )
        for (repo_id, object_path, object_type), (l_plus, l_minus, modifications) in sorted(totals.items())
    ]


def aggregate_author_metrics(
    metrics: Iterable[ObjectMetric],
    commit_hashes: Iterable[str] | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    author: str | None = None,
    path: str | None = None,
) -> list[AuthorMetric]:
    """Aggregate author modifications, churn, and ownership over a commit set H.

    Filter semantics mirror :func:`aggregate_commit_set`: ``author`` restricts
    H to one author's commits (so only that author's rows are produced) and
    ``path`` restricts which objects are reported without shrinking H.
    """

    selected_hashes = set(commit_hashes) if commit_hashes is not None else None
    normalized_path = _normalize_path_filter(path)
    selected_commits: set[str] = set()
    object_churn: dict[tuple[str, str, ObjectType], int] = defaultdict(int)
    author_totals: dict[tuple[str, str, ObjectType, str], list[int]] = defaultdict(lambda: [0, 0])

    for metric in metrics:
        if not _commit_set_filters(metric, selected_hashes, start_time, end_time, author):
            continue
        selected_commits.add(metric.commit_hash)
        if normalized_path is not None and not _path_matches(metric.object_path, normalized_path):
            continue
        object_key = (metric.repo_id, metric.object_path, metric.object_type)
        metric_author = metric.author_identity
        object_churn[object_key] += metric.churn
        author_key = (*object_key, metric_author)
        if metric.churn > 0:
            author_totals[author_key][0] += 1
        author_totals[author_key][1] += metric.churn

    commit_count = len(selected_hashes) if selected_hashes is not None else len(selected_commits)

    return [
        AuthorMetric(
            repo_id=repo_id,
            object_path=object_path,
            object_type=object_type,
            author=author_name,
            commit_count=commit_count,
            total_churn=object_churn[(repo_id, object_path, object_type)],
            modifications=modifications,
            author_churn=author_churn,
        )
        for (repo_id, object_path, object_type, author_name), (modifications, author_churn) in sorted(
            author_totals.items()
        )
    ]


def distinct_authors(metrics: Iterable[ObjectMetric]) -> list[str]:
    """Return the sorted, de-duplicated list of author identities in ``metrics``."""

    authors = {metric.author_identity for metric in metrics if metric.author_identity}
    return sorted(authors)
