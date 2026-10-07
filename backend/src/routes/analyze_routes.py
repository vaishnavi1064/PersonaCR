"""
Analyze routes — Layer 1 fingerprint extraction.

POST /api/analyze-repo            synchronous (waits for the whole analysis)
POST /api/analyze-jobs            background: enqueue on the RQ "analyze" queue (202)
GET  /api/analyze-jobs/{job_id}   job status / stage / result
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from backend.src.core import analysis_store, job_store, rate_limit
from backend.src.core.analysis import AnalysisError, run_analysis
from backend.src.core.auth import AuthUser, current_user
from backend.src.core.analyze_queue import enqueue_analyze_job
from backend.src.core.embedder import delete_guest_collections
from backend.src.core.models import StatusResponse
from backend.src.core.repo_identity import repo_identity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["fingerprint"])


class AnalyzeRequest(BaseModel):
    # No user_id: the caller is the access token's subject (core/auth.py).
    repo_url: str
    github_token: str | None = None
    force_refresh: bool = False


@router.post("/analyze-repo", operation_id="analyze_repo")
def analyze_repo(payload: AnalyzeRequest, user: AuthUser = Depends(current_user)) -> dict:
    """
    Analyze a GitHub repository to build a developer's coding fingerprint.

    Extracts 30+ code features including function length, error handling rate,
    naming conventions, docstring coverage, comment density, complexity metrics,
    and indentation style. Stores code embeddings in ChromaDB for similarity
    search during reviews. Caches the fingerprint in Supabase keyed to the
    latest commit SHA — repeated calls are instant if the repo hasn't changed.

    Must be called before review_code — the fingerprint is required for
    personalized review. Use force_refresh=true to re-analyze after new commits.
    Synchronous; POST /api/analyze-jobs runs the same analysis in the background.
    """
    rate_limit.enforce(user.user_id, rate_limit.ANALYZE)
    try:
        return run_analysis(
            payload.repo_url,
            user_id=user.user_id,
            github_token=payload.github_token,
            force_refresh=payload.force_refresh,
        )
    except AnalysisError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


class AnalyzeJobResponse(BaseModel):
    job_id: str
    repo_url: str
    state: str
    analysis: dict | None = None


@router.post("/analyze-jobs", operation_id="enqueue_analysis", response_model=AnalyzeJobResponse, status_code=202)
def enqueue_analysis(
    payload: AnalyzeRequest, response: Response, user: AuthUser = Depends(current_user)
) -> AnalyzeJobResponse:
    """
    Analyze a repo in the background (RQ worker). Returns immediately with a
    job id; poll GET /api/analyze-jobs/{job_id}, or read the repo's `analysis`
    in GET /api/repos. A repeat request while one is queued/running returns it.
    """
    user_id = user.user_id
    repo_url = analysis_store.normalize_url(payload.repo_url)
    try:
        repo_identity(repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        existing = analysis_store.get_record(user_id, repo_url)
    except Exception as e:
        logger.warning("Analysis queue unavailable: %s", e)
        raise HTTPException(status_code=503, detail="Background analysis is unavailable (job queue offline).")
    if existing and existing.get("state") in analysis_store.ACTIVE_STATES:
        response.status_code = 200
        return AnalyzeJobResponse(
            job_id=existing["job_id"], repo_url=repo_url, state=existing["state"],
            analysis=analysis_store.public_view(existing),
        )
    # Only new jobs count — re-attaching to a running one is free.
    rate_limit.enforce(user_id, rate_limit.ANALYZE)

    job_id = str(uuid.uuid4())
    job_store.create_job(job_id, message="queued", meta={"kind": "analyze", "repo_url": repo_url, "user_id": user_id})
    record = analysis_store.start_record(user_id, repo_url, job_id, force=payload.force_refresh)
    try:
        enqueue_analyze_job(job_id, {
            "repo_url": repo_url,
            "user_id": user_id,
            "force_refresh": payload.force_refresh,
            "github_token": payload.github_token,
        })
    except Exception as e:
        logger.exception("Failed to enqueue analyze job %s", job_id)
        job_store.update_job(job_id, state="failed", progress=100, message="enqueue failed", error=str(e))
        analysis_store.update_record(user_id, repo_url, state="failed", error="Could not queue the analysis.")
        raise HTTPException(status_code=503, detail=f"Could not enqueue analysis: {e}")

    return AnalyzeJobResponse(job_id=job_id, repo_url=repo_url, state="queued", analysis=analysis_store.public_view(record))


@router.get("/analyze-jobs/{job_id}", operation_id="get_analysis_job", response_model=StatusResponse)
def get_analysis_job(job_id: str, user: AuthUser = Depends(current_user)) -> StatusResponse:
    """Background analysis status: state, progress, stage message; result when completed."""
    try:
        job = job_store.get_owned_job(job_id, user.user_id)
    except Exception:
        raise HTTPException(status_code=503, detail="Background analysis is unavailable (job queue offline).")
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return job


@router.delete("/cleanup-guest/{session_id}", operation_id="cleanup_guest")
def cleanup_guest(session_id: str, user: AuthUser = Depends(current_user)) -> dict:
    """
    Wipe all ChromaDB collections for the caller's own guest session.
    Called with a keepalive request when the guest closes their tab or signs out.
    """
    if not session_id.startswith("guest_"):
        return {"deleted": 0, "message": "Not a guest session — nothing to do."}
    if session_id != user.user_id:
        raise HTTPException(status_code=403, detail="You can only clean up your own guest session.")
    deleted = delete_guest_collections(session_id)
    logger.info("Cleaned up %d guest collections for %s", deleted, session_id)
    return {"deleted": deleted, "message": f"Removed {deleted} collection(s) for guest session."}


@router.post("/cleanup-guest/{session_id}", operation_id="cleanup_guest_beacon", include_in_schema=False)
def cleanup_guest_beacon(session_id: str, user: AuthUser = Depends(current_user)) -> dict:
    """
    Same as DELETE /cleanup-guest/{session_id}, as POST for keepalive requests on
    tab close. Hidden from the schema so MCP exposes a single tool.
    """
    return cleanup_guest(session_id, user)
