"""Command-line interface for RAT metric engine base extraction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import MetricEngine, write_deltas_jsonl, write_deltas_tsv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract per-commit per-file l_plus/l_minus deltas from git history.",
    )
    parser.add_argument("repo_path", help="Path to a git repository")
    parser.add_argument("--ref", default="HEAD", help="Reference commit/branch to analyze (default: HEAD)")
    parser.add_argument("--repo-id", default=None, help="Repository identifier to include in output")
    parser.add_argument(
        "--format",
        choices=("tsv", "jsonl"),
        default="tsv",
        help="Output format (default: tsv)",
    )
    parser.add_argument("--output", "-o", default="-", help="Output file path, or '-' for stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine = MetricEngine(repo_path=args.repo_path, ref=args.ref, repo_id=args.repo_id)
    writer = write_deltas_jsonl if args.format == "jsonl" else write_deltas_tsv

    if args.output == "-":
        writer(engine.iter_file_deltas(), sys.stdout)
    else:
        output_path = Path(args.output)
        with output_path.open("w", encoding="utf-8", newline="") as output:
            writer(engine.iter_file_deltas(), output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
