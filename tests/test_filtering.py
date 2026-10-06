"""Tests for docs/05-filtering.md: time, author, path, commit, and composed filters.

Filters are implemented as query parameters over the precomputed per-commit
object metrics (never a re-walk of history), per the engine's own
"compute once at ingestion" architectural rule.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rat_metric_engine import MetricEngine, aggregate_author_metrics, aggregate_commit_set, distinct_authors


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def commit(repo: Path, message: str, author_name: str, author_email: str, date: str) -> str:
    import os

    git(repo, "add", "--all")
    env = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    result = subprocess.run(
        [
            "git",
            "-c",
            f"user.name={author_name}",
            "-c",
            f"user.email={author_email}",
            "commit",
            "--quiet",
            "--author",
            f"{author_name} <{author_email}>",
            "--date",
            date,
            "--message",
            message,
        ],
        cwd=repo,
        check=True,
        text=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0
    return git(repo, "rev-parse", "HEAD")


def build_filtering_fixture(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A small repo with two authors, two directories, spread over distinct days."""

    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet")

    (repo / "src").mkdir()
    (repo / "docs").mkdir()
    (repo / "src" / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    (repo / "docs" / "readme.md").write_text("hello\n", encoding="utf-8")
    commits = {"initial": commit(repo, "initial", "Alice", "alice@example.com", "2020-01-01T00:00:00+00:00")}

    (repo / "src" / "app.py").write_text("one\ntwo changed\nthree\n", encoding="utf-8")
    commits["alice_src"] = commit(repo, "alice edits src", "Alice", "alice@example.com", "2020-02-01T00:00:00+00:00")

    (repo / "docs" / "readme.md").write_text("hello\nworld\n", encoding="utf-8")
    commits["bob_docs"] = commit(repo, "bob edits docs", "Bob", "bob@example.com", "2020-03-01T00:00:00+00:00")

    return repo, commits



def to_unix(date_str: str) -> int:
    import datetime

    return int(datetime.datetime.fromisoformat(date_str).replace(tzinfo=datetime.timezone.utc).timestamp())


def test_time_period_filter_h_t_and_h_i_j(tmp_path: Path) -> None:
    repo, commits = build_filtering_fixture(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())

    # H_t: from 2020-02-01 to present -> excludes the initial commit only.
    h_t = aggregate_commit_set(metrics, start_time=to_unix("2020-02-01"))
    repo_metric = next(m for m in h_t if m.object_type == "repository")
    assert repo_metric.commit_count == 2

    # H_{i,j}: i inclusive, j exclusive -> only the alice_src commit falls in range.
    h_ij = aggregate_commit_set(
        metrics,
        start_time=to_unix("2020-02-01"),
        end_time=to_unix("2020-03-01"),
    )
    repo_metric = next(m for m in h_ij if m.object_type == "repository")
    assert repo_metric.commit_count == 1
    assert repo_metric.l_plus == 2 and repo_metric.l_minus == 1


def test_author_filter_restricts_commit_set_and_metrics(tmp_path: Path) -> None:
    repo, commits = build_filtering_fixture(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())

    assert distinct_authors(metrics) == ["Alice <alice@example.com>", "Bob <bob@example.com>"]

    alice_only = aggregate_commit_set(metrics, author="Alice <alice@example.com>")
    repo_metric = next(m for m in alice_only if m.object_type == "repository")
    assert repo_metric.commit_count == 2  # initial + alice_src

    # "docs" was created by Alice's initial commit (1 line), but Bob's later
    # addition (1 more line) must not leak into Alice's totals.
    docs_metric = next(m for m in alice_only if m.object_path == "docs" and m.object_type == "directory")
    assert (docs_metric.l_plus, docs_metric.l_minus) == (1, 0)


def test_path_filter_exact_file_and_directory_prefix(tmp_path: Path) -> None:
    repo, commits = build_filtering_fixture(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())

    src_only = aggregate_commit_set(metrics, path="src")
    assert {m.object_path for m in src_only} == {"src", "src/app.py"}

    file_only = aggregate_commit_set(metrics, path="src/app.py")
    assert {m.object_path for m in file_only} == {"src/app.py"}


def test_path_filter_does_not_shrink_commit_set_size(tmp_path: Path) -> None:
    """|H| must reflect the time/author/hash filters, not which objects are shown."""

    repo, commits = build_filtering_fixture(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())

    all_commits = aggregate_commit_set(metrics)
    docs_only = aggregate_commit_set(metrics, path="docs")

    repo_wide_count = next(m for m in all_commits if m.object_type == "repository").commit_count
    docs_metric = next(m for m in docs_only if m.object_path == "docs")
    assert docs_metric.commit_count == repo_wide_count == 3


def test_commit_hash_filter_selects_exact_subset(tmp_path: Path) -> None:
    repo, commits = build_filtering_fixture(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())

    one_commit = aggregate_commit_set(metrics, commit_hashes=[commits["bob_docs"]])
    repo_metric = next(m for m in one_commit if m.object_type == "repository")
    assert repo_metric.commit_count == 1
    assert (repo_metric.l_plus, repo_metric.l_minus) == (1, 0)


def test_manual_commit_list_matches_commit_hash_filter_mechanism(tmp_path: Path) -> None:
    """Manual commit-list selection (5.5) uses the same commit_hashes mechanism as 5.4."""

    repo, commits = build_filtering_fixture(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())

    manual_list = [commits["initial"], commits["bob_docs"]]
    selected = aggregate_commit_set(metrics, commit_hashes=manual_list)
    repo_metric = next(m for m in selected if m.object_type == "repository")
    assert repo_metric.commit_count == 2
    # initial adds src(2) + docs(1) = 3 lines; bob_docs adds 1 more docs line.
    assert (repo_metric.l_plus, repo_metric.l_minus) == (4, 0)


def test_filters_compose_with_and_logic(tmp_path: Path) -> None:
    repo, commits = build_filtering_fixture(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())

    # Alice AND time-window AND path=src -> only alice_src's src/app.py change.
    composed = aggregate_commit_set(
        metrics,
        author="Alice <alice@example.com>",
        start_time=to_unix("2020-01-15"),
        end_time=to_unix("2020-03-01"),
        path="src",
    )
    app_py = next(m for m in composed if m.object_path == "src/app.py")
    assert (app_py.l_plus, app_py.l_minus) == (2, 1)
    assert app_py.commit_count == 1

    # Same filters but author=Bob yields nothing (Bob never touched src in that window).
    composed_bob = aggregate_commit_set(
        metrics,
        author="Bob <bob@example.com>",
        start_time=to_unix("2020-01-15"),
        end_time=to_unix("2020-03-01"),
        path="src",
    )
    assert composed_bob == []


def test_author_metrics_support_path_and_time_filters(tmp_path: Path) -> None:
    repo, commits = build_filtering_fixture(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())

    author_metrics = aggregate_author_metrics(metrics, path="docs")
    docs_metric = next(m for m in author_metrics if m.object_path == "docs" and m.author == "Bob <bob@example.com>")
    # docs total churn = Alice's initial add (1) + Bob's add (1) = 2; Bob owns half.
    assert docs_metric.author_churn == 1
    assert docs_metric.total_churn == 2
    assert docs_metric.ownership == 0.5
