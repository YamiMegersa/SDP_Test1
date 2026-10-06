from __future__ import annotations

import json
import subprocess
from pathlib import Path

from rat_metric_engine import MetricEngine, aggregate_author_metrics, aggregate_commit_set, write_deltas_jsonl, write_deltas_tsv
from rat_metric_engine.engine import normalize_rename_path, parse_numstat_line


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


def commit(repo: Path, message: str, author_name: str = "Test User", author_email: str = "test@example.com") -> str:
    git(repo, "add", "--all")
    git(
        repo,
        "-c",
        f"user.name={author_name}",
        "-c",
        f"user.email={author_email}",
        "commit",
        "--quiet",
        "--author",
        f"{author_name} <{author_email}>",
        "--message",
        message,
    )
    return git(repo, "rev-parse", "HEAD")


def build_fixture_repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet")

    (repo / "alpha.txt").write_text("one\ntwo\n", encoding="utf-8")
    commits = {"initial": commit(repo, "initial")}

    (repo / "alpha.txt").write_text("one\ntwo changed\nthree\n", encoding="utf-8")
    commits["modify"] = commit(repo, "modify")

    (repo / "delete_me.txt").write_text("gone one\ngone two\n", encoding="utf-8")
    commits["add_delete_target"] = commit(repo, "add delete target")

    (repo / "delete_me.txt").unlink()
    commits["delete"] = commit(repo, "delete")

    (repo / "image.bin").write_bytes(b"\x00\x01\x02\x03")
    commits["binary"] = commit(repo, "binary")

    git(repo, "mv", "alpha.txt", "renamed.txt")
    commits["pure_rename"] = commit(repo, "pure rename")

    (repo / "renamed.txt").write_text("one\ntwo changed\nthree\nfour\n", encoding="utf-8")
    git(repo, "mv", "renamed.txt", "final.txt")
    commits["rename_with_edit"] = commit(repo, "rename with edit")

    return repo, commits


def test_parse_numstat_skips_binary_and_normalizes_renames() -> None:
    assert parse_numstat_line("-\t-\timage.bin") is None
    assert parse_numstat_line("3\t1\tsrc/file.py") == ("src/file.py", 3, 1)
    assert parse_numstat_line("0\t0\told.txt => new.txt") == ("new.txt", 0, 0)
    assert normalize_rename_path("src/{old.txt => new.txt}") == "src/new.txt"
    assert normalize_rename_path("{old => new}/file.txt") == "new/file.txt"


def test_history_traversal_is_oldest_first(tmp_path: Path) -> None:
    repo, commits = build_fixture_repo(tmp_path)
    history = list(MetricEngine(repo, repo_id="fixture").iter_commits())

    assert [commit.commit_hash for commit in history] == list(commits.values())
    assert history[0].parent_hash is None
    assert history[1].parent_hash == commits["initial"]


def test_file_deltas_cover_initial_delete_binary_and_renames(tmp_path: Path) -> None:
    repo, commits = build_fixture_repo(tmp_path)
    deltas = list(MetricEngine(repo, repo_id="fixture").iter_file_deltas())
    by_commit_path = {(delta.commit_hash, delta.file_path): delta for delta in deltas}

    initial = by_commit_path[(commits["initial"], "alpha.txt")]
    assert (initial.l_plus, initial.l_minus) == (2, 0)

    modified = by_commit_path[(commits["modify"], "alpha.txt")]
    assert (modified.l_plus, modified.l_minus) == (2, 1)

    deleted = by_commit_path[(commits["delete"], "delete_me.txt")]
    assert (deleted.l_plus, deleted.l_minus) == (0, 2)

    assert all(delta.file_path != "image.bin" for delta in deltas)

    pure_rename = by_commit_path[(commits["pure_rename"], "renamed.txt")]
    assert (pure_rename.l_plus, pure_rename.l_minus) == (0, 0)

    edited_rename = by_commit_path[(commits["rename_with_edit"], "final.txt")]
    assert (edited_rename.l_plus, edited_rename.l_minus) == (1, 0)


def test_writers_stream_tsv_and_jsonl(tmp_path: Path) -> None:
    repo, _commits = build_fixture_repo(tmp_path)
    engine = MetricEngine(repo, repo_id="fixture")

    tsv_path = tmp_path / "deltas.tsv"
    with tsv_path.open("w", encoding="utf-8") as output:
        write_deltas_tsv(engine.iter_file_deltas(), output)
    tsv_lines = tsv_path.read_text(encoding="utf-8").splitlines()
    assert tsv_lines[0] == "repo_id\tcommit_hash\tcommitter_date\tfile_path\tl_plus\tl_minus"
    assert any("\tfinal.txt\t1\t0" in line for line in tsv_lines)

    jsonl_path = tmp_path / "deltas.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as output:
        write_deltas_jsonl(MetricEngine(repo, repo_id="fixture").iter_file_deltas(), output)
    records = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert {"repo_id", "commit_hash", "committer_date", "file_path", "l_plus", "l_minus"} <= records[0].keys()


def test_file_metrics_add_growth_and_churn(tmp_path: Path) -> None:
    repo, commits = build_fixture_repo(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_file_metrics())
    by_commit_path = {(metric.commit_hash, metric.object_path): metric for metric in metrics}

    modified = by_commit_path[(commits["modify"], "alpha.txt")]
    assert (modified.l_plus, modified.l_minus, modified.growth, modified.churn) == (2, 1, 1, 3)

    deleted = by_commit_path[(commits["delete"], "delete_me.txt")]
    assert (deleted.l_plus, deleted.l_minus, deleted.growth, deleted.churn) == (0, 2, -2, 2)


def test_directory_and_repository_metrics_roll_up_nested_paths(tmp_path: Path) -> None:
    repo = tmp_path / "nested"
    repo.mkdir()
    git(repo, "init", "--quiet")
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("print('one')\nprint('two')\n", encoding="utf-8")
    (repo / "src" / "pkg" / "mod.py").write_text("value = 1\n", encoding="utf-8")
    initial = commit(repo, "initial nested")

    metrics = list(MetricEngine(repo, repo_id="nested").iter_object_metrics())
    by_path_type = {(metric.commit_hash, metric.object_path, metric.object_type): metric for metric in metrics}

    src = by_path_type[(initial, "src", "directory")]
    src_pkg = by_path_type[(initial, "src/pkg", "directory")]
    repository = by_path_type[(initial, ".", "repository")]

    assert (src.l_plus, src.l_minus, src.growth, src.churn) == (3, 0, 3, 3)
    assert (src_pkg.l_plus, src_pkg.l_minus, src_pkg.growth, src_pkg.churn) == (1, 0, 1, 1)
    assert (repository.l_plus, repository.l_minus) == (src.l_plus, src.l_minus)


def test_commit_set_metrics_sum_modifications_frequency_and_churn_rate(tmp_path: Path) -> None:
    repo, commits = build_fixture_repo(tmp_path)
    metrics = list(MetricEngine(repo, repo_id="fixture").iter_object_metrics())

    alpha_metrics = aggregate_commit_set(metrics, commit_hashes=[commits["initial"], commits["modify"]])
    alpha = next(metric for metric in alpha_metrics if metric.object_path == "alpha.txt" and metric.object_type == "file")
    assert (alpha.l_plus, alpha.l_minus, alpha.growth, alpha.churn) == (4, 1, 3, 5)
    assert alpha.modifications == 2
    assert alpha.modification_frequency == 1.0
    assert alpha.churn_rate == 2.5

    all_metrics = aggregate_commit_set(metrics, commit_hashes=commits.values())
    repository = next(metric for metric in all_metrics if metric.object_path == "." and metric.object_type == "repository")
    assert (repository.l_plus, repository.l_minus, repository.modifications) == (7, 3, 5)
    assert repository.commit_count == len(commits)
    assert repository.modification_frequency == 5 / len(commits)
    assert repository.churn_rate == 10 / len(commits)


def test_author_metrics_count_author_modifications_churn_and_ownership(tmp_path: Path) -> None:
    repo = tmp_path / "authors"
    repo.mkdir()
    git(repo, "init", "--quiet")
    (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
    alice_commit = commit(repo, "alice initial", "Alice", "alice@example.com")
    (repo / "a.txt").write_text("one changed\ntwo\nthree\n", encoding="utf-8")
    bob_commit = commit(repo, "bob modify", "Bob", "bob@example.com")

    metrics = list(MetricEngine(repo, repo_id="authors").iter_object_metrics())
    author_metrics = aggregate_author_metrics(metrics, commit_hashes=[alice_commit, bob_commit])
    file_metrics = {
        metric.author: metric
        for metric in author_metrics
        if metric.object_path == "a.txt" and metric.object_type == "file"
    }

    alice = file_metrics["Alice <alice@example.com>"]
    bob = file_metrics["Bob <bob@example.com>"]

    assert (alice.modifications, alice.author_churn, alice.total_churn) == (1, 2, 5)
    assert (bob.modifications, bob.author_churn, bob.total_churn) == (1, 3, 5)
    assert alice.ownership == 2 / 5
    assert bob.ownership == 3 / 5
