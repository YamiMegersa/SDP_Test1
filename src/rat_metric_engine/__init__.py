"""RAT metric engine extraction and aggregation package."""

from .aggregation import (
    AuthorMetric,
    CommitSetMetric,
    ObjectMetric,
    aggregate_author_metrics,
    aggregate_commit_set,
    build_commit_object_metrics,
    file_metric_from_delta,
    iter_commit_object_metrics,
    iter_file_metrics,
)
from .engine import CommitInfo, FileDelta, MetricEngine, stream_file_deltas, write_deltas_jsonl, write_deltas_tsv
from .ingestion import IngestionError, IngestionService, RepoMetadata, RepoRegistry

__all__ = [
    "AuthorMetric",
    "CommitInfo",
    "CommitSetMetric",
    "FileDelta",
    "IngestionError",
    "IngestionService",
    "MetricEngine",
    "ObjectMetric",
    "RepoMetadata",
    "RepoRegistry",
    "aggregate_author_metrics",
    "aggregate_commit_set",
    "build_commit_object_metrics",
    "file_metric_from_delta",
    "iter_commit_object_metrics",
    "iter_file_metrics",
    "stream_file_deltas",
    "write_deltas_jsonl",
    "write_deltas_tsv",
]
