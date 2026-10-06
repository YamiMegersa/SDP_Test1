from __future__ import annotations

import json
import subprocess
from pathlib import Path
import threading
import zipfile

import pytest

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


def test_multiple_repos_are_listed_and_metric_records_stay_repo_scoped(tmp_path: Path) -> None:
    first_repo = build_small_repo(tmp_path, "first-source")
    second_repo = build_small_repo(tmp_path, "second-source")
    service = IngestionService(RepoRegistry(tmp_path / "registry"))

    first = service.ingest_url(str(first_repo), name="first")
    second = service.ingest_url(str(second_repo), name="second")

    listed = service.list_repos()
    assert [metadata.repo_id for metadata in listed] == sorted([first.repo_id, second.repo_id])
    assert {metadata.name for metadata in listed} == {"first", "second"}

    first_records = read_jsonl(Path(first.metrics_path))
    second_records = read_jsonl(Path(second.metrics_path))
    assert first_records
    assert second_records
    assert {record["repo_id"] for record in first_records} == {first.repo_id}
    assert {record["repo_id"] for record in second_records} == {second.repo_id}
    assert Path(first.metrics_path).parent != Path(second.metrics_path).parent
    assert first.source_path != second.source_path


def test_delete_repo_removes_registry_entry_repo_storage_and_metrics(tmp_path: Path) -> None:
    source_repo = build_small_repo(tmp_path, "source-to-delete")
    service = IngestionService(RepoRegistry(tmp_path / "registry"))
    metadata = service.ingest_url(str(source_repo), name="delete me")
    repo_storage_dir = service.registry.repo_storage_dir(metadata.repo_id)
    metrics_dir = Path(metadata.metrics_path).parent

    deleted = service.delete_repo(metadata.repo_id)

    assert deleted.repo_id == metadata.repo_id
    assert metadata.repo_id not in {repo.repo_id for repo in service.list_repos()}
    assert not repo_storage_dir.exists()
    assert not metrics_dir.exists()
    with pytest.raises(KeyError):
        service.status(metadata.repo_id)


def test_async_ingestion_respects_concurrency_limit_and_queues_excess_work(tmp_path: Path) -> None:
    registry = RepoRegistry(tmp_path / "registry")
    service = IngestionService(registry, max_concurrent_ingestions=1)
    first_started = threading.Event()
    release_first = threading.Event()
    active_count = 0
    peak_active_count = 0
    lock = threading.Lock()

    def fake_worker(repo_id: str, _zip_path: Path):
        nonlocal active_count, peak_active_count
        registry.update(repo_id, status="ingesting")
        with lock:
            active_count += 1
            peak_active_count = max(peak_active_count, active_count)
        if not first_started.is_set():
            first_started.set()
            release_first.wait(timeout=5)
        with lock:
            active_count -= 1
        return registry.update(repo_id, status="ready", commit_count=1)

    service._ingest_zip_worker = fake_worker  # type: ignore[method-assign]

    first = service.ingest_zip(tmp_path / "first.zip", async_mode=True)
    assert first_started.wait(timeout=5)
    second = service.ingest_zip(tmp_path / "second.zip", async_mode=True)

    assert service.status(first.repo_id).status == "ingesting"
    assert service.status(second.repo_id).status == "queued"

    release_first.set()
    assert service.wait_for(first.repo_id, timeout=5).status == "ready"
    assert service.wait_for(second.repo_id, timeout=5).status == "ready"
    assert peak_active_count == 1
