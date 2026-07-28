"""
Review routes — sync + async (Redis/RQ job queue).

POST /api/review      — existing synchronous pipeline (unchanged)
POST /api/reviews     — enqueue async review; returns job_id immediately (202)
GET  /api/reviews/{id} — job status / result (uses StatusResponse / ReportResponse)
"""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from backend.src.agents.orchestrator import review_code_sync
from backend.src.core import job_store
from backend.src.core.cache_manager import get_cached_fingerprint
from backend.src.core.models import ReportResponse, StatusResponse
from backend.src.core.review_queue import enqueue_review_job
from backend.src.db.supabase_rest import SupabaseREST

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["review"])


class CodeReviewRequest(BaseModel):
    repo_url: str
    code: str
    language: str = "python"


class AsyncReviewRequest(BaseModel):
    repo_url: str
    code: str = Field(min_length=1)
    language: str = "python"
    # Queue verification without Groq — not for production clients.
    mock: bool = False
    force_fail: bool = False
    mock_sleep: float = 0.15


def _parse_repo(repo_url: str) -> tuple[str, str, str]:
    repo_url = repo_url.rstrip("/")
    parts = repo_url.split("/")
    if len(parts) < 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid repo URL — expected https://github.com/owner/repo",
        )
    repo_name = parts[-1].removesuffix(".git")
    user_id = parts[-2]
    return repo_url, user_id, repo_name


def _load_fingerprint(repo_url: str, user_id: str, repo_name: str) -> tuple[dict, str]:
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
    return fingerprint, cache_status


@router.post("/review", operation_id="review_code")
def review_code(req: CodeReviewRequest) -> dict:
    """
    Submit code for personalized review against a developer's coding fingerprint.

    Compares the submitted code against the developer's personal patterns (not
    generic rules) using a 6-agent pipeline: Planner selects focus areas,
    Style Analyst finds deviations from the developer's style via ChromaDB
    similarity search, Defect Hunter catches bugs with AST + LLM analysis,
    QA Checker filters irrelevant findings, Confidence Evaluator scores
    retrieval quality, and a CRScore-inspired Layer 3 evaluation computes
    comprehensiveness and conciseness scores via STS (all-MiniLM-L6-v2).

    The repo_url must have been previously analyzed via analyze_repo.
    Returns style deviations, defects, quality scores, and full agent traces.

    Synchronous path — prefer POST /api/reviews for non-blocking jobs.
    """
    repo_url, user_id, repo_name = _parse_repo(req.repo_url)
    fingerprint, cache_status = _load_fingerprint(repo_url, user_id, repo_name)

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


@router.post(
    "/reviews",
    operation_id="enqueue_review",
    response_model=StatusResponse,
    status_code=202,
)
def enqueue_review(req: AsyncReviewRequest, response: Response) -> StatusResponse:
    """
    Enqueue an async review job (Redis-backed RQ queue).

    Returns immediately with job_id (HTTP 202). Poll GET /api/reviews/{job_id}.
    Set mock=true to exercise the queue without calling Groq.
    """
    repo_url, user_id, repo_name = _parse_repo(req.repo_url)

    payload: dict = {
        "repo_url": repo_url,
        "code": req.code,
        "language": req.language,
        "mock": req.mock,
        "force_fail": req.force_fail,
        "mock_sleep": req.mock_sleep,
    }

    if not req.mock:
        fingerprint, cache_status = _load_fingerprint(repo_url, user_id, repo_name)
        payload["fingerprint"] = fingerprint
        payload["fingerprint_cache_status"] = cache_status

    job_id = str(uuid.uuid4())
    status = job_store.create_job(job_id, message="queued")

    try:
        enqueue_review_job(job_id, payload)
    except Exception as e:
        logger.exception("Failed to enqueue review job %s", job_id)
        job_store.update_job(
            job_id,
            state="failed",
            progress=100,
            message="enqueue failed",
            error=str(e),
        )
        raise HTTPException(status_code=503, detail=f"Could not enqueue job: {e}")

    response.status_code = 202
    return status


@router.get(
    "/reviews/{job_id}",
    operation_id="get_review_job",
    response_model=StatusResponse,
)
def get_review_job(job_id: str) -> StatusResponse:
    """Return async review job status; includes result when completed."""
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return job


@router.get(
    "/reviews/{job_id}/report",
    operation_id="get_review_report",
    response_model=ReportResponse,
)
def get_review_report(job_id: str) -> ReportResponse:
    """Return ReportResponse when the job has completed (orphaned model wired)."""
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    report = job_store.to_report_response(job)
    if report is None:
        raise HTTPException(
            status_code=409,
            detail=f"Job not completed (state={job.state})",
        )
    return report
