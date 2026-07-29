"""
RQ job functions for async reviews.

Real path runs review_code_sync unchanged. Mock/fail flags exist so queue
mechanics can be verified without Groq.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from backend.src.core import job_store

logger = logging.getLogger(__name__)

QUEUE_NAME = "reviews"


def _canned_result(repo_url: str, language: str) -> dict[str, Any]:
    return {
        "repo_url": repo_url,
        "language": language,
        "fingerprint_cache_status": "mock",
        "overall_score": 88.0,
        "status": "passed",
        "iterations": 1,
        "issues_count": 0,
        "issues": [],
        "review_output": {
            "mock": True,
            "summary": "Canned mock review — no Groq call.",
        },
        "agent_trace": [],
    }


def process_review_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Worker entry: queued → running → completed | failed.

    payload keys:
      repo_url, code, language, fingerprint (optional dict),
      mock (bool), force_fail (bool), mock_sleep (float)
    """
    job_store.update_job(
        job_id,
        state="running",
        progress=10,
        message="running",
    )
    try:
        if payload.get("force_fail"):
            raise RuntimeError(payload.get("fail_message") or "Forced mock failure")

        if payload.get("mock"):
            sleep_s = float(payload.get("mock_sleep", 0.15))
            time.sleep(sleep_s)
            job_store.update_job(job_id, progress=60, message="mock pipeline")
            result = _canned_result(
                payload.get("repo_url", ""),
                payload.get("language", "python"),
            )
            from backend.src.core.metrics import record_mock_review

            record_mock_review(sleep_s)
        else:
            fingerprint = payload.get("fingerprint")
            if not fingerprint:
                raise ValueError("Missing fingerprint for real review job")
            if isinstance(fingerprint, str):
                fingerprint = json.loads(fingerprint)

            repo_url = payload["repo_url"].rstrip("/")
            parts = repo_url.split("/")
            repo_name = parts[-1].removesuffix(".git")
            user_id = parts[-2]

            job_store.update_job(job_id, progress=30, message="running pipeline")
            from backend.src.agents.orchestrator import review_code_sync

            review = review_code_sync(
                payload["code"],
                payload.get("language", "python"),
                fingerprint,
                user_id,
                repo_name,
            )
            result = {
                "repo_url": repo_url,
                "language": payload.get("language", "python"),
                "fingerprint_cache_status": payload.get(
                    "fingerprint_cache_status", "unknown"
                ),
                "overall_score": review.overall_score,
                "status": review.status,
                "iterations": review.iterations,
                "issues_count": len(review.issues),
                "issues": review.issues,
                "review_output": review.review_output,
                "agent_trace": [t.model_dump() for t in review.agent_trace],
            }

        review_id = str(uuid.uuid4())
        job_store.update_job(
            job_id,
            state="completed",
            progress=100,
            message="completed",
            result=result,
            review_id=review_id,
            error=None,
        )
        return result
    except Exception as exc:
        logger.exception("Review job %s failed", job_id)
        try:
            job_store.update_job(
                job_id,
                state="failed",
                progress=100,
                message="failed",
                error=str(exc),
            )
        except Exception:
            logger.exception("Failed to mark job %s as failed", job_id)
        raise
