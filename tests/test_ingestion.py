from __future__ import annotations

import json
import subprocess
from pathlib import Path
import zipfile

from rat_metric_engine import IngestionService, RepoRegistry


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


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "--all")
    git(
        repo,
        "-c",
        "user.name=Ingest User",
        "-c",
        "user.email=ingest@example.com",
        "commit",
        "--quiet",
        "--author",
        "Ingest User <ingest@example.com>",
        "--message",
        message,
    )
    return git(repo, "rev-parse", "HEAD")


def build_small_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "--quiet")
    (repo / "app.txt").write_text("one\n", encoding="utf-8")
    commit(repo, "initial")
    (repo / "app.txt").write_text("one\ntwo\n", encoding="utf-8")
    commit(repo, "modify")
    return repo


def zip_repo(repo: Path, zip_path: Path, prefix: str = "uploaded-repo") -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in repo.rglob("*"):
            archive.write(path, Path(prefix) / path.relative_to(repo))


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_zip_ingestion_registers_repo_and_runs_metrics(tmp_path: Path) -> None:
    repo = build_small_repo(tmp_path)
    zip_path = tmp_path / "repo.zip"
    zip_repo(repo, zip_path)
    service = IngestionService(RepoRegistry(tmp_path / "registry"))

    metadata = service.ingest_zip(zip_path, name="zipped")

    assert metadata.status == "ready"
    assert metadata.name == "zipped"
    assert metadata.source_type == "zip"
    assert metadata.commit_count == 2
    assert Path(metadata.source_path, ".git", "HEAD").exists()
    assert Path(metadata.metrics_path).exists()
    records = read_jsonl(Path(metadata.metrics_path))
    assert any(record["object_path"] == "app.txt" and record["object_type"] == "file" for record in records)
    assert any(record["object_path"] == "." and record["object_type"] == "repository" for record in records)


def test_url_ingestion_clones_local_repo_and_status_is_queryable(tmp_path: Path) -> None:
    repo = build_small_repo(tmp_path, "source")
    registry = RepoRegistry(tmp_path / "registry")
    service = IngestionService(registry)

    metadata = service.ingest_url(str(repo), name="cloned")
    stored = service.status(metadata.repo_id)

    assert stored.status == "ready"
    assert stored.source_type == "url"
    assert stored.commit_count == 2
    assert Path(stored.source_path, "HEAD").exists()
    assert stored.object_metric_count > 0
    assert registry.get(stored.repo_id).metrics_path == stored.metrics_path


def test_async_zip_ingestion_can_be_polled_and_waited_for(tmp_path: Path) -> None:
    repo = build_small_repo(tmp_path)
    zip_path = tmp_path / "async.zip"
    zip_repo(repo, zip_path)
    service = IngestionService(RepoRegistry(tmp_path / "registry"))

    queued = service.ingest_zip(zip_path, async_mode=True)
    initial_status = service.status(queued.repo_id).status
    completed = service.wait_for(queued.repo_id, timeout=5)

    assert initial_status in {"queued", "ingesting", "ready"}
    assert completed.status == "ready"
    assert completed.commit_count == 2


def test_invalid_zip_is_recorded_as_failed_with_clear_message(tmp_path: Path) -> None:
    invalid_zip = tmp_path / "not-a-zip.zip"
    invalid_zip.write_text("not a zip", encoding="utf-8")
    service = IngestionService(RepoRegistry(tmp_path / "registry"))

    metadata = service.ingest_zip(invalid_zip)

    assert metadata.status == "failed"
    assert "Invalid zip file" in metadata.error_message
    assert service.status(metadata.repo_id).status == "failed"


def test_invalid_url_is_recorded_as_failed_with_clear_message(tmp_path: Path) -> None:
    service = IngestionService(RepoRegistry(tmp_path / "registry"))

    metadata = service.ingest_url("not a url")

    assert metadata.status == "failed"
    assert "Invalid repository URL" in metadata.error_message
    assert service.status(metadata.repo_id).error_message == metadata.error_message
