"""Streaming git history and per-file line-delta extraction.

The engine shells out to git for history traversal and numstat diff extraction. It
keeps only commit metadata in memory and streams per-file deltas as they are
parsed, avoiding full patch diffs entirely.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import subprocess
from pathlib import Path
from typing import Iterable, Iterator, TextIO

from .mailmap import MailmapAliases, load_mailmap, resolve_mailmap_identity


@dataclass(frozen=True)
class CommitInfo:
    """A non-merge commit reachable from a reference."""

    commit_hash: str
    parent_hash: str | None
    committer_date: int
    author_name: str = ""
    author_email: str = ""

    @property
    def author_identity(self) -> str:
        """Stable display identity for the commit author."""

        if self.author_email and self.author_name:
            return f"{self.author_name} <{self.author_email}>"
        return self.author_name or self.author_email


@dataclass(frozen=True)
class FileDelta:
    """Line additions/removals for one file in one commit."""

    repo_id: str
    commit_hash: str
    committer_date: int
    file_path: str
    l_plus: int
    l_minus: int


class GitCommandError(RuntimeError):
    """Raised when a git command fails."""


def _run_git(repo_path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        command = " ".join(["git", *args])
        raise GitCommandError(f"{command} failed in {repo_path}: {result.stderr.strip()}")
    return result


def _iter_git_stdout_lines(repo_path: Path, args: list[str]) -> Iterator[str]:
    process = subprocess.Popen(
        ["git", *args],
        cwd=repo_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        for line in process.stdout:
            yield line.rstrip("\n")
    finally:
        stderr = process.stderr.read()
        return_code = process.wait()
        if return_code != 0:
            command = " ".join(["git", *args])
            raise GitCommandError(f"{command} failed in {repo_path}: {stderr.strip()}")


class MetricEngine:
    """Extract base metric deltas from a git repository."""

    def __init__(
        self,
        repo_path: str | Path,
        ref: str = "HEAD",
        repo_id: str | None = None,
        mailmap: MailmapAliases | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.ref = ref
        self.repo_id = repo_id or self.repo_path.name
        self._ensure_git_repository()
        # Mailmap identity resolution (docs/06-author-merging.md §6.1/6.2) is
        # applied once here, at extraction time, since it is static repo
        # content. Manual merges (user-driven) are applied later, at the
        # aggregation layer, so they stay cheap to change/undo.
        self.mailmap = mailmap if mailmap is not None else load_mailmap(self.repo_path)

    def _ensure_git_repository(self) -> None:
        _run_git(self.repo_path, ["rev-parse", "--git-dir"])

    def iter_commits(self) -> Iterator[CommitInfo]:
        """Yield non-merge commits in oldest-first topological order."""

        field_separator = "\x1f"
        lines = _iter_git_stdout_lines(
            self.repo_path,
            [
                "log",
                "--no-merges",
                "--topo-order",
                "--reverse",
                "--format=%H%x1f%P%x1f%ct%x1f%an%x1f%ae",
                self.ref,
            ],
        )
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split(field_separator)
            if len(parts) != 5:
                raise ValueError(f"Unexpected git log row: {line!r}")
            commit_hash, parents, committer_date, author_name, author_email = parts
            parent_hashes = parents.split()
            parent_hash = parent_hashes[0] if parent_hashes else None
            if self.mailmap:
                author_name, author_email = resolve_mailmap_identity(author_name, author_email, self.mailmap)
            yield CommitInfo(commit_hash, parent_hash, int(committer_date), author_name, author_email)

    def iter_commit_deltas(self, commit: CommitInfo) -> Iterator[FileDelta]:
        """Yield parsed numstat deltas for one commit."""

        args = ["diff-tree", "--no-commit-id", "-r", "-M50", "--numstat"]
        if commit.parent_hash is None:
            args.extend(["--root", commit.commit_hash])
        else:
            args.extend([commit.parent_hash, commit.commit_hash])

        for line in _iter_git_stdout_lines(self.repo_path, args):
            parsed = parse_numstat_line(line)
            if parsed is None:
                continue
            file_path, l_plus, l_minus = parsed
            yield FileDelta(
                repo_id=self.repo_id,
                commit_hash=commit.commit_hash,
                committer_date=commit.committer_date,
                file_path=file_path,
                l_plus=l_plus,
                l_minus=l_minus,
            )

    def iter_file_deltas(self) -> Iterator[FileDelta]:
        """Yield all per-commit per-file deltas for the configured ref."""

        for commit in self.iter_commits():
            yield from self.iter_commit_deltas(commit)

    def iter_file_metrics(self):
        """Yield per-commit file metrics with growth/churn properties."""

        from .aggregation import file_metric_from_delta

        for commit in self.iter_commits():
            for delta in self.iter_commit_deltas(commit):
                yield file_metric_from_delta(delta, commit)

    def iter_object_metrics(self):
        """Yield per-commit file, directory, and repository metrics."""

        from .aggregation import build_commit_object_metrics, file_metric_from_delta

        for commit in self.iter_commits():
            file_metrics = [file_metric_from_delta(delta, commit) for delta in self.iter_commit_deltas(commit)]
            yield from build_commit_object_metrics(file_metrics)


def parse_numstat_line(line: str) -> tuple[str, int, int] | None:
    """Parse a git numstat row.

    Returns ``None`` for binary files, which git reports as ``-`` additions and
    removals. For rename rows, the returned path is normalized to the new path.
    """

    parts = line.split("\t", 2)
    if len(parts) != 3:
        return None
    added, removed, path = parts
    if added == "-" or removed == "-":
        return None
    return normalize_rename_path(path), int(added), int(removed)


def normalize_rename_path(path: str) -> str:
    """Return the postimage path for git's text numstat rename forms."""

    if " => " not in path:
        return path

    # Simple form: old/name.ext => new/name.ext
    if "{" not in path and "}" not in path:
        return path.split(" => ", 1)[1]

    # Brace form: dir/{old => new}/file.ext or {old => new}/file.ext
    open_idx = path.find("{")
    close_idx = path.find("}", open_idx + 1)
    if open_idx == -1 or close_idx == -1:
        return path.split(" => ", 1)[1]

    before = path[:open_idx]
    after = path[close_idx + 1 :]
    inner = path[open_idx + 1 : close_idx]
    if " => " not in inner:
        return path
    _old, new = inner.split(" => ", 1)
    return f"{before}{new}{after}"


def stream_file_deltas(repo_path: str | Path, ref: str = "HEAD", repo_id: str | None = None) -> Iterator[FileDelta]:
    """Convenience generator for all deltas in a repository."""

    yield from MetricEngine(repo_path=repo_path, ref=ref, repo_id=repo_id).iter_file_deltas()


def write_deltas_tsv(deltas: Iterable[FileDelta], output: TextIO) -> None:
    """Write deltas as a tab-separated stream with a header row."""

    output.write("repo_id\tcommit_hash\tcommitter_date\tfile_path\tl_plus\tl_minus\n")
    for delta in deltas:
        output.write(
            f"{delta.repo_id}\t{delta.commit_hash}\t{delta.committer_date}\t"
            f"{delta.file_path}\t{delta.l_plus}\t{delta.l_minus}\n"
        )


def write_deltas_jsonl(deltas: Iterable[FileDelta], output: TextIO) -> None:
    """Write deltas as newline-delimited JSON records."""

    for delta in deltas:
        output.write(json.dumps(asdict(delta), separators=(",", ":")) + "\n")
