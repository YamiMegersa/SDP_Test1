"""Repository ingestion pipeline for zip uploads and clone URLs.

The ingestion layer is deliberately framework-agnostic: a web endpoint, CLI, or test
can pass a zip path or URL into :class:`IngestionService`. The service stores repo
metadata in a small JSON registry, verifies the repository, and triggers the
existing metric engine/aggregation pipeline without changing that lower layer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import threading
from typing import Literal
from urllib.parse import urlparse
from uuid import uuid4
import zipfile

from .engine import GitCommandError, MetricEngine

SourceType = Literal["zip", "url"]
IngestionStatus = Literal["queued", "ingesting", "ready", "failed"]


class IngestionError(RuntimeError):
    """Raised for user-facing ingestion failures."""


@dataclass(frozen=True)
class RepoMetadata:
    """Stored metadata for one ingested repository."""

    repo_id: str
    name: str
    source_type: SourceType
    source_path: str
    ingested_at: str
    commit_count: int = 0
    status: IngestionStatus = "queued"
    metrics_path: str = ""
    object_metric_count: int = 0
    error_message: str = ""


class RepoRegistry:
    """JSON-backed repository registry.

    The registry is intentionally small and dependency-free. It gives the future
    multi-repo feature a stable shape while remaining easy to inspect in tests.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.repos_dir = self.base_dir / "repos"
        self.metrics_dir = self.base_dir / "metrics"
        self.registry_path = self.base_dir / "repos.json"
        self._lock = threading.Lock()
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        source_type: SourceType,
        name: str,
        source_path: str = "",
        repo_id: str | None = None,
        status: IngestionStatus = "queued",
    ) -> RepoMetadata:
        metadata = RepoMetadata(
            repo_id=repo_id or uuid4().hex,
            name=name,
            source_type=source_type,
            source_path=source_path,
            ingested_at=utc_now_iso(),
            status=status,
        )
        self.save(metadata)
        return metadata

    def save(self, metadata: RepoMetadata) -> RepoMetadata:
        with self._lock:
            records = self._load_records()
            records[metadata.repo_id] = asdict(metadata)
            self._write_records(records)
        return metadata

    def update(self, repo_id: str, **changes: object) -> RepoMetadata:
        with self._lock:
            records = self._load_records()
            if repo_id not in records:
                raise KeyError(f"Unknown repo_id: {repo_id}")
            records[repo_id].update(changes)
            metadata = RepoMetadata(**records[repo_id])
            self._write_records(records)
        return metadata

    def get(self, repo_id: str) -> RepoMetadata:
        records = self._load_records()
        if repo_id not in records:
            raise KeyError(f"Unknown repo_id: {repo_id}")
        return RepoMetadata(**records[repo_id])

    def list(self) -> list[RepoMetadata]:
        records = self._load_records()
        return [RepoMetadata(**records[repo_id]) for repo_id in sorted(records)]

    def repo_storage_dir(self, repo_id: str) -> Path:
        return self.repos_dir / repo_id

    def object_metrics_path(self, repo_id: str) -> Path:
        return self.metrics_dir / repo_id / "object_metrics.jsonl"

    def _load_records(self) -> dict[str, dict[str, object]]:
        if not self.registry_path.exists():
            return {}
        with self.registry_path.open("r", encoding="utf-8") as input_file:
            return json.load(input_file)

    def _write_records(self, records: dict[str, dict[str, object]]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.registry_path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as output_file:
            json.dump(records, output_file, indent=2, sort_keys=True)
            output_file.write("\n")
        temp_path.replace(self.registry_path)


class IngestionService:
    """Orchestrate zip/URL ingestion and metric precomputation."""

    def __init__(self, registry: RepoRegistry, ref: str = "HEAD") -> None:
        self.registry = registry
        self.ref = ref
        self._threads: dict[str, threading.Thread] = {}

    def ingest_zip(self, zip_path: str | Path, name: str | None = None, async_mode: bool = False) -> RepoMetadata:
        zip_path = Path(zip_path).resolve()
        metadata = self.registry.create("zip", name or zip_path.stem)
        if async_mode:
            self._start_worker(metadata.repo_id, self._ingest_zip_worker, zip_path)
            return self.registry.get(metadata.repo_id)
        return self._ingest_zip_worker(metadata.repo_id, zip_path)

    def ingest_url(self, url: str, name: str | None = None, async_mode: bool = False) -> RepoMetadata:
        repo_name = name or derive_repo_name_from_url(url)
        metadata = self.registry.create("url", repo_name)
        if async_mode:
            self._start_worker(metadata.repo_id, self._ingest_url_worker, url)
            return self.registry.get(metadata.repo_id)
        return self._ingest_url_worker(metadata.repo_id, url)

    def status(self, repo_id: str) -> RepoMetadata:
        return self.registry.get(repo_id)

    def wait_for(self, repo_id: str, timeout: float | None = None) -> RepoMetadata:
        thread = self._threads.get(repo_id)
        if thread is not None:
            thread.join(timeout=timeout)
        return self.registry.get(repo_id)

    def _start_worker(self, repo_id: str, target, *args: object) -> None:
        thread = threading.Thread(target=target, args=(repo_id, *args), daemon=True)
        self._threads[repo_id] = thread
        thread.start()

    def _ingest_zip_worker(self, repo_id: str, zip_path: Path) -> RepoMetadata:
        repo_dir = self.registry.repo_storage_dir(repo_id)
        extract_dir = repo_dir / "extracted"
        try:
            self.registry.update(repo_id, status="ingesting")
            if not zip_path.exists():
                raise IngestionError(f"Zip file does not exist: {zip_path}")
            safe_extract_zip(zip_path, extract_dir)
            source_path = find_worktree_repo_root(extract_dir)
            verify_git_repository(source_path)
            self.registry.update(repo_id, source_path=str(source_path))
            return self._run_metrics(repo_id, source_path)
        except (IngestionError, OSError, zipfile.BadZipFile, GitCommandError) as exc:
            cleanup_path(repo_dir)
            return self._mark_failed(repo_id, user_facing_error(exc))

    def _ingest_url_worker(self, repo_id: str, url: str) -> RepoMetadata:
        repo_dir = self.registry.repo_storage_dir(repo_id)
        clone_path = repo_dir / "repo.git"
        try:
            self.registry.update(repo_id, status="ingesting")
            validate_clone_url(url)
            clone_mirror(url, clone_path)
            verify_git_repository(clone_path)
            self.registry.update(repo_id, source_path=str(clone_path))
            return self._run_metrics(repo_id, clone_path)
        except (IngestionError, OSError, GitCommandError) as exc:
            cleanup_path(repo_dir)
            return self._mark_failed(repo_id, user_facing_error(exc))

    def _run_metrics(self, repo_id: str, source_path: Path) -> RepoMetadata:
        metrics_path = self.registry.object_metrics_path(repo_id)
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        engine = MetricEngine(source_path, ref=self.ref, repo_id=repo_id)
        commit_count = len(list(engine.iter_commits()))
        object_metric_count = 0
        with metrics_path.open("w", encoding="utf-8") as output_file:
            for metric in MetricEngine(source_path, ref=self.ref, repo_id=repo_id).iter_object_metrics():
                output_file.write(json.dumps(asdict(metric), separators=(",", ":")) + "\n")
                object_metric_count += 1
        return self.registry.update(
            repo_id,
            status="ready",
            commit_count=commit_count,
            metrics_path=str(metrics_path),
            object_metric_count=object_metric_count,
            error_message="",
        )

    def _mark_failed(self, repo_id: str, message: str) -> RepoMetadata:
        return self.registry.update(repo_id, status="failed", error_message=message)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    """Extract a zip without allowing path traversal."""

    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                member_path = safe_zip_member_path(member.filename)
                target_path = (destination / member_path).resolve()
                if not target_path.is_relative_to(destination.resolve()):
                    raise IngestionError(f"Unsafe zip member path: {member.filename}")
                if member.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                    continue
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target_path.open("wb") as target:
                    shutil.copyfileobj(source, target)
    except zipfile.BadZipFile as exc:
        raise IngestionError("Invalid zip file: could not read archive") from exc


def safe_zip_member_path(filename: str) -> Path:
    pure_path = PurePosixPath(filename)
    if pure_path.is_absolute() or any(part in ("..", "") for part in pure_path.parts):
        raise IngestionError(f"Unsafe zip member path: {filename}")
    return Path(*pure_path.parts)


def find_worktree_repo_root(search_root: Path) -> Path:
    """Find a non-bare git worktree root under an extracted zip."""

    candidates = []
    for head_path in search_root.rglob("HEAD"):
        if head_path.parent.name == ".git":
            candidates.append(head_path.parent.parent)
    if not candidates:
        raise IngestionError("Zip archive does not contain a git repository with .git/HEAD")
    return sorted(candidates, key=lambda path: len(path.relative_to(search_root).parts))[0]


def validate_clone_url(url: str) -> None:
    value = url.strip()
    if not value:
        raise IngestionError("Repository URL is required")
    if Path(value).exists():
        return
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https", "ssh", "git"} and parsed.netloc:
        return
    if parsed.scheme == "file" and parsed.path:
        return
    if re.match(r"^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+:.+", value):
        return
    raise IngestionError("Invalid repository URL: expected http(s), ssh, git, file, scp-style, or local path")


def clone_mirror(url: str, clone_path: Path) -> None:
    clone_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--mirror", url, str(clone_path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git clone failed"
        raise IngestionError(f"Could not clone repository: {message}")


def verify_git_repository(repo_path: str | Path) -> None:
    path = Path(repo_path)
    if not ((path / ".git" / "HEAD").exists() or (path / "HEAD").exists()):
        raise IngestionError("Repository is missing .git/HEAD or bare HEAD")
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=path,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise IngestionError(f"Invalid git repository: {result.stderr.strip()}")


def derive_repo_name_from_url(url: str) -> str:
    value = url.rstrip("/")
    parsed = urlparse(value)
    candidate = Path(parsed.path if parsed.scheme else value).name
    if not candidate and ":" in value:
        candidate = value.rsplit(":", 1)[1].rstrip("/").split("/")[-1]
    if candidate.endswith(".git"):
        candidate = candidate[:-4]
    return candidate or "repository"


def cleanup_path(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def user_facing_error(exc: BaseException) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__
