"""Tests for docs/06-author-merging.md: mailmap parsing, identity resolution,
manual merge persistence/re-aggregation, un-merge, and the web merge UI.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rat_metric_engine import (
    IngestionService,
    MetricEngine,
    RepoRegistry,
    aggregate_author_metrics,
    aggregate_commit_set,
    distinct_authors,
    resolve_author_identity,
)
from rat_metric_engine.mailmap import parse_mailmap_text, resolve_mailmap_identity
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


# ---------------------------------------------------------------------------
# 6.1 Mailmap parsing
# ---------------------------------------------------------------------------


def test_parse_mailmap_simple_name_only_declares_no_alias() -> None:
    aliases = parse_mailmap_text("Jane Doe <jane@example.com>\n")
    assert aliases == {}


def test_parse_mailmap_canonical_with_commit_email() -> None:
    aliases = parse_mailmap_text("Jane Doe <jane@example.com> <jane.old@example.com>\n")
    assert aliases == {"jane.old@example.com": ("Jane Doe", "jane@example.com")}


def test_parse_mailmap_canonical_with_commit_name_and_email() -> None:
    aliases = parse_mailmap_text(
        "Jane Doe <jane@example.com> Jane D <jane.d@example.com>\n"
    )
    assert aliases == {"jane.d@example.com": ("Jane Doe", "jane@example.com")}


def test_parse_mailmap_ignores_comments_and_blank_lines() -> None:
    text = "# comment\n\nJane Doe <jane@example.com> <jane.old@example.com>\n"
    aliases = parse_mailmap_text(text)
    assert aliases == {"jane.old@example.com": ("Jane Doe", "jane@example.com")}


def test_parse_mailmap_email_matching_is_case_insensitive_on_lookup() -> None:
    aliases = parse_mailmap_text("Jane Doe <jane@example.com> <Jane.Old@Example.com>\n")
    name, email = resolve_mailmap_identity("Jane Old", "jane.old@example.com", aliases)
    assert (name, email) == ("Jane Doe", "jane@example.com")


def test_resolve_mailmap_identity_falls_back_when_no_alias() -> None:
    aliases = parse_mailmap_text("Jane Doe <jane@example.com> <jane.old@example.com>\n")
    name, email = resolve_mailmap_identity("Bob", "bob@example.com", aliases)
    assert (name, email) == ("Bob", "bob@example.com")


# ---------------------------------------------------------------------------
# 6.2 Identity resolution — mailmap applied end-to-end through MetricEngine
# ---------------------------------------------------------------------------


def test_metric_engine_applies_repo_mailmap_to_commit_authors(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet")

    (repo / ".mailmap").write_text(
        "Jane Doe <jane@example.com> <jane.old@example.com>\n", encoding="utf-8"
    )
    (repo / "app.txt").write_text("one\n", encoding="utf-8")
    commit(repo, "initial", "Jane Doe", "jane@example.com", "2020-01-01T00:00:00+00:00")

    (repo / "app.txt").write_text("one\ntwo\n", encoding="utf-8")
    commit(repo, "old-email edit", "Jane Old", "jane.old@example.com", "2020-01-02T00:00:00+00:00")

    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())
    authors = distinct_authors(metrics)

    # Both commits resolve to the same canonical identity via .mailmap.
    assert authors == ["Jane Doe <jane@example.com>"]


# ---------------------------------------------------------------------------
# 6.3 / 6.5 Manual merge applied at the aggregation layer (query time)
# ---------------------------------------------------------------------------


def build_two_author_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "--quiet")

    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("one\n", encoding="utf-8")
    commit(repo, "initial", "Alice", "alice@example.com", "2020-01-01T00:00:00+00:00")

    (repo / "src" / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    commit(repo, "alice-work-account edit", "Alice W", "alice.work@example.com", "2020-01-02T00:00:00+00:00")

    return repo


def test_resolve_author_identity_follows_chain_with_cycle_guard() -> None:
    merges = {"a": "b", "b": "c", "cycle1": "cycle2", "cycle2": "cycle1"}
    assert resolve_author_identity("a", merges) == "c"
    assert resolve_author_identity("unmapped", merges) == "unmapped"
    # A malformed cyclic mapping must terminate rather than loop forever.
    assert resolve_author_identity("cycle1", merges) in {"cycle1", "cycle2"}


def test_distinct_authors_applies_manual_merges(tmp_path: Path) -> None:
    repo = build_two_author_fixture(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())

    raw = distinct_authors(metrics)
    assert raw == ["Alice <alice@example.com>", "Alice W <alice.work@example.com>"]

    merges = {"Alice W <alice.work@example.com>": "Alice <alice@example.com>"}
    merged = distinct_authors(metrics, author_merges=merges)
    assert merged == ["Alice <alice@example.com>"]


def test_aggregate_author_metrics_sums_merged_identities(tmp_path: Path) -> None:
    repo = build_two_author_fixture(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())
    merges = {"Alice W <alice.work@example.com>": "Alice <alice@example.com>"}

    author_metrics = aggregate_author_metrics(metrics, author_merges=merges)
    repo_entry = next(m for m in author_metrics if m.object_type == "repository")

    assert repo_entry.author == "Alice <alice@example.com>"
    # initial (+1) + alice-work edit (+1) both attributed to the merged author.
    assert repo_entry.author_churn == 2
    assert repo_entry.modifications == 2
    assert repo_entry.ownership == 1.0


def test_aggregate_commit_set_author_filter_matches_canonical_identity(tmp_path: Path) -> None:
    repo = build_two_author_fixture(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())
    merges = {"Alice W <alice.work@example.com>": "Alice <alice@example.com>"}

    filtered = aggregate_commit_set(metrics, author="Alice <alice@example.com>", author_merges=merges)
    repo_entry = next(m for m in filtered if m.object_type == "repository")
    assert repo_entry.commit_count == 2  # both commits now count as Alice's


# ---------------------------------------------------------------------------
# 6.4 / 6.6 Merge persistence and un-merge via RepoRegistry
# ---------------------------------------------------------------------------


def test_registry_merge_and_unmerge_authors_persist(tmp_path: Path) -> None:
    registry = RepoRegistry(tmp_path / "registry")
    registry.create("url", "repo", repo_id="repo-1")

    assert registry.get_author_merges("repo-1") == {}

    registry.merge_authors("repo-1", ["Bob <bob@old.com>", "Bob <bob@older.com>"], "Bob <bob@new.com>")
    merges = registry.get_author_merges("repo-1")
    assert merges == {
        "Bob <bob@old.com>": "Bob <bob@new.com>",
        "Bob <bob@older.com>": "Bob <bob@new.com>",
    }

    # Persists across a fresh RepoRegistry instance pointed at the same dir.
    reloaded = RepoRegistry(tmp_path / "registry")
    assert reloaded.get_author_merges("repo-1") == merges

    reloaded.unmerge_author("repo-1", "Bob <bob@old.com>")
    assert reloaded.get_author_merges("repo-1") == {"Bob <bob@older.com>": "Bob <bob@new.com>"}


def test_merge_authors_ignores_self_mapping(tmp_path: Path) -> None:
    registry = RepoRegistry(tmp_path / "registry")
    registry.create("url", "repo", repo_id="repo-1")

    registry.merge_authors("repo-1", ["Alice <a@example.com>"], "Alice <a@example.com>")
    assert registry.get_author_merges("repo-1") == {}


def test_delete_repo_removes_author_merges_file(tmp_path: Path) -> None:
    source_repo = build_two_author_fixture(tmp_path / "source")
    service = IngestionService(RepoRegistry(tmp_path / "registry"))
    metadata = service.ingest_url(str(source_repo), name="repo")

    service.registry.merge_authors(
        metadata.repo_id, ["Alice W <alice.work@example.com>"], "Alice <alice@example.com>"
    )
    merges_path = service.registry.author_merges_path(metadata.repo_id)
    assert merges_path.exists()

    service.delete_repo(metadata.repo_id)
    assert not merges_path.exists()


# ---------------------------------------------------------------------------
# Web UI: authors page, merge, unmerge, and filtered metrics after merging
# ---------------------------------------------------------------------------


def make_app_with_two_author_repo(tmp_path: Path):
    source_repo = build_two_author_fixture(tmp_path / "source")
    registry = RepoRegistry(tmp_path / "registry")
    service = IngestionService(registry)
    metadata = service.ingest_url(str(source_repo), name="merge-repo")
    assert metadata.status == "ready"

    app = create_app(tmp_path / "registry")
    return app, metadata


def test_repo_authors_page_lists_raw_authors(tmp_path: Path) -> None:
    app, metadata = make_app_with_two_author_repo(tmp_path)
    client = app.test_client()

    response = client.get(f"/repo/{metadata.repo_id}/authors")
    assert response.status_code == 200
    assert b"Alice &lt;alice@example.com&gt;" in response.data or b"Alice <alice@example.com>" in response.data
    assert b"alice.work@example.com" in response.data


def test_merge_authors_via_web_route_persists_and_updates_metrics(tmp_path: Path) -> None:
    app, metadata = make_app_with_two_author_repo(tmp_path)
    client = app.test_client()

    merge_response = client.post(
        f"/repo/{metadata.repo_id}/authors/merge",
        data={
            "aliases": ["Alice W <alice.work@example.com>"],
            "canonical": "Alice <alice@example.com>",
        },
    )
    assert merge_response.status_code == 302

    # The authors page now shows one canonical group with the merged alias.
    authors_page = client.get(f"/repo/{metadata.repo_id}/authors")
    assert b"Alice &lt;alice@example.com&gt;" in authors_page.data or b"Alice <alice@example.com>" in authors_page.data

    # Dashboard author dropdown/filter now reports one combined author.
    metrics_response = client.get(f"/repo/{metadata.repo_id}/metrics")
    assert metrics_response.data.count(b"Alice W <alice.work@example.com>") == 0 or b"Alice &lt;alice@example.com&gt;" in metrics_response.data

    filtered = client.get(
        f"/repo/{metadata.repo_id}/metrics?author=Alice+%3Calice%40example.com%3E"
    )
    assert filtered.status_code == 200
    assert b"<code>src/app.py</code>" in filtered.data


def test_unmerge_authors_via_web_route_reverts(tmp_path: Path) -> None:
    app, metadata = make_app_with_two_author_repo(tmp_path)
    client = app.test_client()

    client.post(
        f"/repo/{metadata.repo_id}/authors/merge",
        data={
            "aliases": ["Alice W <alice.work@example.com>"],
            "canonical": "Alice <alice@example.com>",
        },
    )
    unmerge_response = client.post(
        f"/repo/{metadata.repo_id}/authors/unmerge",
        data={"alias": "Alice W <alice.work@example.com>"},
    )
    assert unmerge_response.status_code == 302

    api_response = client.get(f"/api/repos/{metadata.repo_id}/metrics")
    payload = api_response.get_json()
    assert sorted(payload["authors"]) == [
        "Alice <alice@example.com>",
        "Alice W <alice.work@example.com>",
    ]


def test_merge_authors_requires_canonical_and_aliases(tmp_path: Path) -> None:
    app, metadata = make_app_with_two_author_repo(tmp_path)
    client = app.test_client()

    missing_canonical = client.post(f"/repo/{metadata.repo_id}/authors/merge", data={"aliases": ["Alice"]})
    assert missing_canonical.status_code == 400

    missing_aliases = client.post(
        f"/repo/{metadata.repo_id}/authors/merge", data={"canonical": "Alice <alice@example.com>"}
    )
    assert missing_aliases.status_code == 400
