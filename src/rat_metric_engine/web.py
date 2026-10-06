"""Flask web application for RAT dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from .aggregation import ObjectMetric, aggregate_author_metrics, aggregate_commit_set, distinct_authors, resolve_author_identity
from .engine import MetricEngine
from .ingestion import IngestionService, RepoRegistry

DEFAULT_REGISTRY_DIR = Path("./rat_data")


class FilterError(ValueError):
    """Raised when filter query parameters cannot be parsed."""


def parse_filters(args) -> dict[str, object]:
    """Parse filter query parameters (docs/05-filtering.md) from a request.

    Supported params: ``start_date``/``end_date`` (``YYYY-MM-DD``, ``i``
    inclusive / ``j`` exclusive per the brief's ``H_{i,j}``), ``author``,
    ``path``, and ``commits`` (comma/whitespace-separated hashes, used for
    both the commit-hash filter and the manual commit-list picker).
    """

    import datetime

    def parse_date(value: str, *, end_of_day: bool = False) -> int:
        try:
            parsed = datetime.datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        except ValueError as exc:
            raise FilterError(f"Invalid date (expected YYYY-MM-DD): {value!r}") from exc
        if end_of_day:
            parsed += datetime.timedelta(days=1)
        return int(parsed.timestamp())

    start_date = (args.get("start_date") or "").strip()
    end_date = (args.get("end_date") or "").strip()
    author = (args.get("author") or "").strip()
    path = (args.get("path") or "").strip()
    commits_raw = (args.get("commits") or "").strip()

    commit_hashes = None
    if commits_raw:
        commit_hashes = sorted({token.strip() for token in commits_raw.replace(",", " ").split() if token.strip()})

    return {
        "start_date": start_date or None,
        "end_date": end_date or None,
        "start_time": parse_date(start_date) if start_date else None,
        # end_date is inclusive from the user's point of view, so the
        # exclusive upper bound `j` used by H_{i,j} is the start of the next day.
        "end_time": parse_date(end_date, end_of_day=True) if end_date else None,
        "author": author or None,
        "path": path or None,
        "commits": commits_raw or None,
        "commit_hashes": commit_hashes,
    }



def load_object_metrics(metadata) -> list[ObjectMetric]:
    """Load and reconstruct raw per-commit object metrics for a ready repo."""

    if metadata.status != "ready" or not metadata.metrics_path:
        return []
    metrics_path = Path(metadata.metrics_path)
    if not metrics_path.exists():
        return []
    records = [json.loads(line) for line in metrics_path.read_text(encoding="utf-8").splitlines()]
    return [ObjectMetric(**record) for record in records]


def has_active_filters(filters: dict[str, object]) -> bool:
    return any(filters.get(key) for key in ("start_date", "end_date", "author", "path", "commits"))



def create_app(registry_dir: str | Path | None = None) -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__, template_folder="templates", static_folder="static")
    registry_dir = Path(registry_dir) if registry_dir else DEFAULT_REGISTRY_DIR
    registry = RepoRegistry(registry_dir)
    ingestion_service = IngestionService(registry)

    app.config["registry"] = registry
    app.config["ingestion_service"] = ingestion_service

    register_routes(app, registry, ingestion_service)
    return app


def register_routes(app: Flask, registry: RepoRegistry, ingestion: IngestionService) -> None:
    """Register all routes on the Flask app."""

    @app.route("/")
    def index():
        """Dashboard home: list all ingested repositories."""

        repos = registry.list()
        return render_template("index.html", repos=repos)

    @app.route("/ingest", methods=["GET"])
    def ingest_form():
        """Show ingestion form (zip upload or URL clone)."""

        return render_template("ingest.html")

    @app.route("/ingest/zip", methods=["POST"])
    def ingest_zip():
        """Handle zip file upload and ingestion."""

        if "file" not in request.files:
            return Response("No file uploaded", status=400)
        file = request.files["file"]
        if file.filename == "":
            return Response("No file selected", status=400)

        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            file.save(tmp.name)
            metadata = ingestion.ingest_zip(tmp.name, name=file.filename, async_mode=True)

        return redirect(url_for("repo_status", repo_id=metadata.repo_id))

    @app.route("/ingest/url", methods=["POST"])
    def ingest_url():
        """Handle URL clone and ingestion."""

        url = request.form.get("url", "").strip()
        if not url:
            return Response("URL is required", status=400)

        metadata = ingestion.ingest_url(url, async_mode=True)
        return redirect(url_for("repo_status", repo_id=metadata.repo_id))

    @app.route("/repo/<repo_id>")
    def repo_status(repo_id: str):
        """Show repository status and metrics."""

        try:
            metadata = registry.get(repo_id)
        except KeyError:
            return Response("Repository not found", status=404)

        return render_template("repo.html", repo=metadata)

    @app.route("/repo/<repo_id>/metrics")
    def repo_metrics(repo_id: str):
        """Show detailed, filterable metrics for a repository (docs/05-filtering.md)."""

        try:
            metadata = registry.get(repo_id)
        except KeyError:
            return Response("Repository not found", status=404)

        try:
            filters = parse_filters(request.args)
        except FilterError as exc:
            return Response(str(exc), status=400)

        object_metrics = load_object_metrics(metadata)
        if not object_metrics:
            return render_template(
                "repo_metrics.html",
                repo=metadata,
                metrics=None,
                author_metrics=[],
                authors=[],
                filters=filters,
                active=False,
            )

        author_merges = registry.get_author_merges(repo_id)
        authors = distinct_authors(object_metrics, author_merges=author_merges)
        metrics = aggregate_commit_set(
            object_metrics,
            commit_hashes=filters["commit_hashes"],
            start_time=filters["start_time"],
            end_time=filters["end_time"],
            author=filters["author"],
            path=filters["path"],
            author_merges=author_merges,
        )
        author_metrics = [
            metric
            for metric in aggregate_author_metrics(
                object_metrics,
                commit_hashes=filters["commit_hashes"],
                start_time=filters["start_time"],
                end_time=filters["end_time"],
                author=filters["author"],
                path=filters["path"],
                author_merges=author_merges,
            )
            if metric.object_type == "repository"
        ]
        return render_template(
            "repo_metrics.html",
            repo=metadata,
            metrics=metrics,
            author_metrics=author_metrics,
            authors=authors,
            filters=filters,
            active=has_active_filters(filters),
        )

    @app.route("/api/repos")
    def api_list_repos():
        """API: list all repositories."""

        repos = registry.list()
        return jsonify([
            {
                "repo_id": repo.repo_id,
                "name": repo.name,
                "status": repo.status,
                "commit_count": repo.commit_count,
                "object_metric_count": repo.object_metric_count,
                "ingested_at": repo.ingested_at,
            }
            for repo in repos
        ])

    @app.route("/api/repos/<repo_id>")
    def api_get_repo(repo_id: str):
        """API: get repository metadata."""

        try:
            repo = registry.get(repo_id)
        except KeyError:
            return Response(json.dumps({"error": "Repository not found"}), status=404, mimetype="application/json")

        return jsonify({
            "repo_id": repo.repo_id,
            "name": repo.name,
            "status": repo.status,
            "source_type": repo.source_type,
            "source_path": repo.source_path,
            "commit_count": repo.commit_count,
            "object_metric_count": repo.object_metric_count,
            "ingested_at": repo.ingested_at,
            "metrics_path": repo.metrics_path,
        })

    @app.route("/api/repos/<repo_id>/metrics")
    def api_get_metrics(repo_id: str):
        """API: get metrics for a repository, optionally filtered (docs/05-filtering.md).

        Supports the same query params as the dashboard filter UI: start_date,
        end_date, author, path, commits. With no filters, returns the full
        per-object aggregation over the whole history (equivalent to H̄).
        """

        try:
            repo = registry.get(repo_id)
        except KeyError:
            return Response(json.dumps({"error": "Repository not found"}), status=404, mimetype="application/json")

        try:
            filters = parse_filters(request.args)
        except FilterError as exc:
            return Response(json.dumps({"error": str(exc)}), status=400, mimetype="application/json")

        object_metrics = load_object_metrics(repo)
        if not object_metrics:
            return jsonify({"metrics": [], "authors": []})

        author_merges = registry.get_author_merges(repo_id)
        aggregated = aggregate_commit_set(
            object_metrics,
            commit_hashes=filters["commit_hashes"],
            start_time=filters["start_time"],
            end_time=filters["end_time"],
            author=filters["author"],
            path=filters["path"],
            author_merges=author_merges,
        )
        return jsonify(
            {
                "metrics": [
                    {
                        "repo_id": metric.repo_id,
                        "object_path": metric.object_path,
                        "object_type": metric.object_type,
                        "commit_count": metric.commit_count,
                        "l_plus": metric.l_plus,
                        "l_minus": metric.l_minus,
                        "growth": metric.growth,
                        "churn": metric.churn,
                        "modifications": metric.modifications,
                        "modification_frequency": metric.modification_frequency,
                        "churn_rate": metric.churn_rate,
                    }
                    for metric in aggregated
                ],
                "authors": distinct_authors(object_metrics, author_merges=author_merges),
            }
        )

    @app.route("/repo/<repo_id>/authors")
    def repo_authors(repo_id: str):
        """Author merge management page (docs/06-author-merging.md).

        Lists the repo's raw (post-mailmap) author identities grouped by
        their current canonical identity, so authors can be merged or
        un-merged.
        """

        try:
            metadata = registry.get(repo_id)
        except KeyError:
            return Response("Repository not found", status=404)

        object_metrics = load_object_metrics(metadata)
        merges = registry.get_author_merges(repo_id)
        raw_authors = distinct_authors(object_metrics)

        groups: dict[str, list[str]] = {}
        for identity in raw_authors:
            canonical = resolve_author_identity(identity, merges)
            groups.setdefault(canonical, []).append(identity)
        # Canonical identities picked via a custom name won't appear in
        # raw_authors; keep groups sorted by canonical identity for display.
        sorted_groups = dict(sorted(groups.items()))

        return render_template(
            "authors.html",
            repo=metadata,
            raw_authors=raw_authors,
            groups=sorted_groups,
            merges=merges,
        )

    @app.route("/repo/<repo_id>/authors/merge", methods=["POST"])
    def repo_authors_merge(repo_id: str):
        """Merge selected author identities into one canonical identity."""

        try:
            registry.get(repo_id)
        except KeyError:
            return Response("Repository not found", status=404)

        aliases = [alias for alias in request.form.getlist("aliases") if alias]
        canonical = (request.form.get("canonical") or "").strip()
        if not canonical:
            canonical = (request.form.get("canonical_custom") or "").strip()
        if not canonical:
            return Response("A canonical author is required", status=400)
        if not aliases:
            return Response("Select at least one author to merge", status=400)

        registry.merge_authors(repo_id, aliases, canonical)
        return redirect(url_for("repo_authors", repo_id=repo_id))

    @app.route("/repo/<repo_id>/authors/unmerge", methods=["POST"])
    def repo_authors_unmerge(repo_id: str):
        """Undo a single alias's manual merge (docs/06-author-merging.md §6.6)."""

        try:
            registry.get(repo_id)
        except KeyError:
            return Response("Repository not found", status=404)

        alias = (request.form.get("alias") or "").strip()
        if not alias:
            return Response("Alias is required", status=400)

        registry.unmerge_author(repo_id, alias)
        return redirect(url_for("repo_authors", repo_id=repo_id))


