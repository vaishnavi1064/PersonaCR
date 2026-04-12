"""
Review route — POST /api/review

Connects the multi-agent orchestrator to the API.
Looks up the cached fingerprint for the repo, then runs the full
Layer 2 pipeline (Planner → Style Analyst ‖ Defect Hunter → QA → Confidence).
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.src.agents.orchestrator import review_code_sync
from backend.src.core.cache_manager import get_cached_fingerprint
from backend.src.db.supabase_rest import SupabaseREST

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["review"])


class CodeReviewRequest(BaseModel):
    repo_url: str
    code: str
    language: str = "python"


@router.post("/review")
def review_code(req: CodeReviewRequest) -> dict:
    """
    Submit code for personalized review against a repo's fingerprint.

    Prerequisites:
      - The repo must have been analyzed via POST /api/analyze-repo first.
        That call ingests code, builds the fingerprint, stores it in Supabase,
        and embeds chunks into ChromaDB.

    Flow:
      1. Parse user_id + repo_name from the URL
      2. Load cached fingerprint from Supabase
      3. Run the orchestrator (Planner → Style ‖ Defect → QA → Confidence)
      4. Return structured result with agent traces and timing
    """
    repo_url = req.repo_url.rstrip("/")

    # ── Parse user_id and repo_name from URL ─────────────────────────────────
    parts = repo_url.split("/")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid repo URL — expected https://github.com/owner/repo")
    repo_name = parts[-1].removesuffix(".git")
    user_id = parts[-2]

    # ── Load cached fingerprint from Supabase ─────────────────────────────────
    db = SupabaseREST()
    try:
        cached = get_cached_fingerprint(db, repo_url, user_id)
    except Exception as e:
        logger.exception("Supabase lookup failed for %s", repo_url)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    if not cached or not cached.get("fingerprint_data"):
        raise HTTPException(
            status_code=404,
            detail=(
                f"No fingerprint found for {user_id}/{repo_name}. "
                "Analyze the repo first via POST /api/analyze-repo"
            ),
        )

    fingerprint = cached["fingerprint_data"]
    # Supabase may return the JSON column already parsed or as a raw string
    if isinstance(fingerprint, str):
        try:
            fingerprint = json.loads(fingerprint)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"Corrupt fingerprint data: {e}")

    cache_status = cached.get("_cache_status", "unknown")
    if cache_status == "stale":
        logger.warning(
            "Fingerprint for %s is stale (new commits exist). "
            "Review will use the last known fingerprint.",
            repo_url,
        )

    # ── Run multi-agent review ────────────────────────────────────────────────
    logger.info("Starting review for %s/%s (%s)", user_id, repo_name, req.language)
    try:
        result = review_code_sync(req.code, req.language, fingerprint, user_id, repo_name)
    except Exception as e:
        logger.exception("Orchestrator failed for %s", repo_url)
        raise HTTPException(status_code=500, detail=f"Review pipeline failed: {e}")

    logger.info(
        "Review complete — score=%.1f, issues=%d, iterations=%d, status=%s",
        result.overall_score,
        len(result.issues),
        result.iterations,
        result.status,
    )

    return {
        "repo_url": repo_url,
        "language": req.language,
        "fingerprint_cache_status": cache_status,
        "overall_score": result.overall_score,
        "status": result.status,
        "iterations": result.iterations,
        "issues_count": len(result.issues),
        "issues": result.issues,
        "review_output": result.review_output,
        "agent_trace": [t.model_dump() for t in result.agent_trace],
    }
