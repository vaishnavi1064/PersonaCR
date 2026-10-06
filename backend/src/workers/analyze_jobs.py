"""
RQ job for background repo analysis (queue "analyze").

queued → running (stages: fetch / extract / index / save) → completed | failed.
Status goes to two places: the job (job_store, polled by job id) and the
per-user repo record (analysis_store, merged into GET /api/repos).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from backend.src.core import analysis_store, job_store
from backend.src.core.analysis import AnalysisError, run_analysis
from backend.src.core.repo_identity import as_uuid_or_none
from backend.src.db.supabase_rest import SupabaseREST

logger = logging.getLogger(__name__)

QUEUE_NAME = "analyze"
# Big repos fetch files one by one; the RQ default (180 s) is too short.
JOB_TIMEOUT_SECONDS = 30 * 60
# Write progress at most this often (file fetches can be many per second).
_PROGRESS_INTERVAL_S = 1.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_user_repo(user_id: str, result: dict[str, Any]) -> None:
    """Add the repo to the user's list (what the browser used to do after a sync analyze)."""
    uid = as_uuid_or_none(user_id)
    if uid is None:
        return  # guests (guest_<sub>) have no saved list; SupabaseREST would refuse the row anyway
    repo_url = result["repo_url"]
    fp = result.get("fingerprint") or {}
    languages = list((fp.get("language_distribution") or {}).keys()) or fp.get("languages") or []
    SupabaseREST().insert("user_repos", {
        "user_id": uid,
        "repo_url": repo_url,
        "repo_name": "/".join(repo_url.split("/")[-2:]),
        "functions_count": result.get("num_functions", 0),
        "languages": "{" + ",".join(languages) + "}",
    })


def process_analyze_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """payload: repo_url, user_id, force_refresh, github_token (optional)."""
    user_id = payload["user_id"]
    repo_url = payload["repo_url"]
    last_write = 0.0

    def report(stage: str, progress: int, message: str) -> None:
        nonlocal last_write
        now = time.monotonic()
        if now - last_write < _PROGRESS_INTERVAL_S and stage == "fetch":
            return
        last_write = now
        job_store.update_job(job_id, state="running", progress=progress, message=message)
        analysis_store.update_record(user_id, repo_url, state="running", stage=stage, progress=progress, message=message)

    report("start", 2, "Starting")
    try:
        result = run_analysis(
            repo_url,
            user_id=user_id,
            github_token=payload.get("github_token"),
            force_refresh=bool(payload.get("force_refresh")),
            on_stage=report,
        )
        try:
            _record_user_repo(user_id, result)
        except Exception:
            # The fingerprint is saved; the list row is best-effort (dedupe makes retries safe)
            logger.exception("Analyze job %s: could not add %s to user_repos", job_id, repo_url)

        summary = {
            "num_functions": result.get("num_functions"),
            "cache_status": result.get("cache_status"),
            "analyzed_at": result.get("analyzed_at"),
            "last_commit_sha": result.get("last_commit_sha"),
            "index_error": (result.get("embedding") or {}).get("error"),
            # Guests' fingerprints aren't saved to the database — keep them with the record
            "fingerprint": result.get("fingerprint") if user_id.startswith("guest_") else None,
        }
        job_store.update_job(job_id, state="completed", progress=100, message="completed", result=result, error=None)
        analysis_store.update_record(
            user_id, repo_url, state="completed", stage="done", progress=100, message="Done",
            finished_at=_now(), summary=summary, error=None,
        )
        return result
    except Exception as exc:
        detail = exc.detail if isinstance(exc, AnalysisError) else f"Analysis failed: {exc}"
        if not isinstance(exc, AnalysisError):
            logger.exception("Analyze job %s failed", job_id)
        try:
            job_store.update_job(job_id, state="failed", progress=100, message="failed", error=detail)
            analysis_store.update_record(
                user_id, repo_url, state="failed", stage="failed", message="Failed", error=detail, finished_at=_now(),
            )
        except Exception:
            logger.exception("Failed to mark analyze job %s as failed", job_id)
        raise
