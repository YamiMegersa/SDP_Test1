"""End-to-end tests for the RAT web dashboard, focused on filtering (docs/05-filtering.md).

Uses Flask's test client against a real ingested fixture repo so filters are
exercised through the full stack: ingestion -> stored metrics -> web routes.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rat_metric_engine import IngestionService, RepoRegistry
from rat_metric_engine.web import create_app


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
    git(repo, "add", "--all")
    env = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    subprocess.run(
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
    )
    return git(repo, "rev-parse", "HEAD")


def build_dashboard_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "dash-repo"
    repo.mkdir(parents=True)
    git(repo, "init", "--quiet")

    (repo / "src").mkdir()
    (repo / "docs").mkdir()
    (repo / "src" / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    (repo / "docs" / "readme.md").write_text("hello\n", encoding="utf-8")
    commit(repo, "initial", "Alice", "alice@example.com", "2020-01-01T00:00:00+00:00")

    (repo / "src" / "app.py").write_text("one\ntwo changed\nthree\n", encoding="utf-8")
    commit(repo, "alice edits src", "Alice", "alice@example.com", "2020-02-01T00:00:00+00:00")

    (repo / "docs" / "readme.md").write_text("hello\nworld\n", encoding="utf-8")
    commit(repo, "bob edits docs", "Bob", "bob@example.com", "2020-03-01T00:00:00+00:00")

    return repo


def make_app_with_ready_repo(tmp_path: Path):
    source_repo = build_dashboard_fixture(tmp_path / "source")
    registry = RepoRegistry(tmp_path / "registry")
    service = IngestionService(registry)
    metadata = service.ingest_url(str(source_repo), name="dashboard-repo")
    assert metadata.status == "ready"

    app = create_app(tmp_path / "registry")
    return app, metadata


def assert_path_shown(data: bytes, path: str) -> None:
    assert f"<code>{path}</code>".encode() in data


def assert_path_not_shown(data: bytes, path: str) -> None:
    assert f"<code>{path}</code>".encode() not in data


def test_index_lists_ready_repo(tmp_path: Path) -> None:
    app, metadata = make_app_with_ready_repo(tmp_path)
    client = app.test_client()

    response = client.get("/")
    assert response.status_code == 200
    assert b"dashboard-repo" in response.data


def test_repo_metrics_with_no_filters_shows_full_history(tmp_path: Path) -> None:
    app, metadata = make_app_with_ready_repo(tmp_path)
    client = app.test_client()

    response = client.get(f"/repo/{metadata.repo_id}/metrics")
    assert response.status_code == 200
    assert_path_shown(response.data, "src/app.py")
    assert_path_shown(response.data, "docs/readme.md")
    assert b"Commits in Set" in response.data


def test_repo_metrics_time_filter_narrows_results(tmp_path: Path) -> None:
    app, metadata = make_app_with_ready_repo(tmp_path)
    client = app.test_client()

    response = client.get(f"/repo/{metadata.repo_id}/metrics?start_date=2020-02-15&end_date=2020-03-02")
    assert response.status_code == 200
    # Only Bob's docs edit (2020-03-01) falls in this window; Alice's src edit (2020-02-01) must not.
    assert_path_shown(response.data, "docs/readme.md")
    assert_path_not_shown(response.data, "src/app.py")


def test_repo_metrics_author_filter(tmp_path: Path) -> None:
    app, metadata = make_app_with_ready_repo(tmp_path)
    client = app.test_client()

    response = client.get(f"/repo/{metadata.repo_id}/metrics?author=Bob+%3Cbob%40example.com%3E")
    assert response.status_code == 200
    assert_path_shown(response.data, "docs/readme.md")
    assert_path_not_shown(response.data, "src/app.py")
    # Author dropdown should list both known authors regardless of filter applied.
    assert b"Alice &lt;alice@example.com&gt;" in response.data or b"Alice <alice@example.com>" in response.data


def test_repo_metrics_path_filter(tmp_path: Path) -> None:
    app, metadata = make_app_with_ready_repo(tmp_path)
    client = app.test_client()

    response = client.get(f"/repo/{metadata.repo_id}/metrics?path=src")
    assert response.status_code == 200
    assert_path_shown(response.data, "src/app.py")
    assert_path_not_shown(response.data, "docs/readme.md")


def test_repo_metrics_commit_filter_manual_list(tmp_path: Path) -> None:
    app, metadata = make_app_with_ready_repo(tmp_path)
    client = app.test_client()

    engine_metrics_response = client.get(f"/api/repos/{metadata.repo_id}/metrics")
    assert engine_metrics_response.status_code == 200

    # Pull one commit hash via the raw stored metrics file to drive the manual list filter.
    import json

    records = [json.loads(line) for line in Path(metadata.metrics_path).read_text(encoding="utf-8").splitlines()]
    src_commits = {r["commit_hash"] for r in records if r["object_path"] == "src/app.py"}
    bob_hash = next(
        r["commit_hash"]
        for r in records
        if r["object_path"] == "docs/readme.md" and r["commit_hash"] not in src_commits
    )

    response = client.get(f"/repo/{metadata.repo_id}/metrics?commits={bob_hash}")
    assert response.status_code == 200
    assert_path_shown(response.data, "docs/readme.md")
    assert_path_not_shown(response.data, "src/app.py")


def test_repo_metrics_filters_compose_with_and_logic(tmp_path: Path) -> None:
    app, metadata = make_app_with_ready_repo(tmp_path)
    client = app.test_client()

    response = client.get(
        f"/repo/{metadata.repo_id}/metrics?author=Alice+%3Calice%40example.com%3E&path=docs"
    )
    assert response.status_code == 200
    # Alice touched docs only via the initial commit; nothing from Bob should appear.
    assert_path_shown(response.data, "docs")
    assert b"world" not in response.data  # sanity: file content never echoed



def test_repo_metrics_clear_filters_link_present_when_active(tmp_path: Path) -> None:
    app, metadata = make_app_with_ready_repo(tmp_path)
    client = app.test_client()

    filtered = client.get(f"/repo/{metadata.repo_id}/metrics?path=src")
    assert b"Clear all filters" in filtered.data

    unfiltered = client.get(f"/repo/{metadata.repo_id}/metrics")
    assert b"Clear all filters" not in unfiltered.data


def test_repo_metrics_invalid_date_returns_400(tmp_path: Path) -> None:
    app, metadata = make_app_with_ready_repo(tmp_path)
    client = app.test_client()

    response = client.get(f"/repo/{metadata.repo_id}/metrics?start_date=not-a-date")
    assert response.status_code == 400


def test_api_metrics_endpoint_supports_filters_and_returns_json(tmp_path: Path) -> None:
    app, metadata = make_app_with_ready_repo(tmp_path)
    client = app.test_client()

    response = client.get(f"/api/repos/{metadata.repo_id}/metrics?path=src")
    assert response.status_code == 200
    payload = response.get_json()
    assert {m["object_path"] for m in payload["metrics"]} == {"src", "src/app.py"}
    assert sorted(payload["authors"]) == ["Alice <alice@example.com>", "Bob <bob@example.com>"]


def test_api_metrics_endpoint_unfiltered_matches_full_history(tmp_path: Path) -> None:
    app, metadata = make_app_with_ready_repo(tmp_path)
    client = app.test_client()

    response = client.get(f"/api/repos/{metadata.repo_id}/metrics")
    payload = response.get_json()
    repo_entry = next(m for m in payload["metrics"] if m["object_type"] == "repository")
    assert repo_entry["commit_count"] == 3
    # initial: +2 (src) +1 (docs) = +3; alice edit: +2/-1; bob edit: +1 -> total +6/-1
    assert (repo_entry["l_plus"], repo_entry["l_minus"]) == (6, 1)
