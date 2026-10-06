"""
Repo analysis — one implementation for the sync route (POST /api/analyze-repo)
and the background job (POST /api/analyze-jobs → RQ "analyze" queue).

ingest → fingerprint → embed → save. Reports progress through ``on_stage``.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from backend.src.core.cache_manager import get_cached_fingerprint, save_fingerprint
from backend.src.core.embedder import embed_and_store
from backend.src.core.github_ingestor import ingest_repo
from backend.src.core.pattern_extractor import extract_fingerprint
from backend.src.core.repo_identity import repo_identity
from backend.src.db.supabase_rest import SupabaseREST

logger = logging.getLogger(__name__)

# on_stage(stage, progress 0–100, message)
StageCallback = Callable[[str, int, str], None]


class AnalysisError(Exception):
    """Analysis failed in a way the caller should report (HTTP status + message)."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _noop(stage: str, progress: int, message: str) -> None:
    pass


def run_analysis(
    repo_url: str,
    user_id: str = "anonymous",
    github_token: str | None = None,
    force_refresh: bool = False,
    on_stage: StageCallback | None = None,
) -> dict[str, Any]:
    """Analyze a GitHub repo; returns the analyze-repo response dict. Raises AnalysisError."""
    stage = on_stage or _noop
    db = SupabaseREST()
    repo_url = repo_url.rstrip("/")

    # ── Cache ────────────────────────────────────────────────────────────────
    if not force_refresh:
        stage("cache", 5, "Checking for a saved analysis")
        cached = get_cached_fingerprint(db, repo_url, user_id, github_token)
        if cached and cached.get("_cache_status") == "fresh":
            return {
                "repo_url": repo_url,
                "repo_name": cached.get("repo_name", ""),
                "fingerprint": cached.get("fingerprint_data", {}),
                "num_functions": cached.get("num_functions", 0),
                "last_commit_sha": cached.get("last_commit_sha", ""),
                "analyzed_at": cached.get("updated_at"),
                "cache_status": "fresh",
                "message": "Loaded from cache — repo unchanged since last analysis.",
                "embedding": {"status": "cached", "collection": None, "chunks_embedded": 0, "error": None},
            }

    # ── Ingest ───────────────────────────────────────────────────────────────
    stage("fetch", 10, "Fetching files from GitHub")

    def on_files(done: int, total: int) -> None:
        # 10 → 60% while fetching files
        pct = 10 + int(50 * done / total) if total else 60
        stage("fetch", pct, f"Fetching files {done}/{total}")

    try:
        chunks, latest_sha = ingest_repo(repo_url, github_token, on_progress=on_files)
    except ValueError as e:
        raise AnalysisError(400, str(e)) from e
    except Exception as e:
        raise AnalysisError(500, f"Ingestion failed: {e}") from e

    if not chunks:
        raise AnalysisError(422, "No code functions found in this repo.")

    stage("extract", 62, "Extracting conventions")
    fingerprint = extract_fingerprint(chunks)

    # Per-repo identity: the collection is keyed on the repo (owner/name), not on who
    # analyzed it, so reviews by any user hit the same vectors.
    try:
        owner, repo_name = repo_identity(repo_url)
    except ValueError as e:
        raise AnalysisError(400, str(e)) from e

    # ── Embed (explicit status — never silent) ───────────────────────────────
    stage("index", 70, f"Indexing {len(chunks)} code chunks for reviews")
    embedding_info: dict[str, Any] = {"status": "skipped", "collection": None, "chunks_embedded": 0, "error": None}
    try:
        emb = embed_and_store(chunks, owner, repo_name, analyzed_by=user_id)
        embedding_info = {
            "status": "ok",
            "collection": emb.get("collection"),
            "chunks_embedded": emb.get("chunks_embedded", 0),
            "error": None,
        }
    except Exception as e:
        logger.exception("ChromaDB embedding failed for %s", repo_url)
        embedding_info = {"status": "failed", "collection": None, "chunks_embedded": 0, "error": str(e)}

    # ── Save — skipped for guest sessions (no persistent account) ────────────
    stage("save", 95, "Saving the fingerprint")
    if not user_id.startswith("guest_"):
        try:
            save_fingerprint(db, repo_url, repo_name, fingerprint, latest_sha, user_id, num_chunks=len(chunks))
        except Exception as e:
            logger.warning("Could not save fingerprint to Supabase: %s", e)

    return {
        "repo_url": repo_url,
        "repo_name": repo_name,
        "fingerprint": fingerprint,
        "num_functions": len(chunks),
        "last_commit_sha": latest_sha,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "cache_status": "new",
        "message": f"Analyzed {len(chunks)} functions from {repo_name}.",
        "embedding": embedding_info,
    }
