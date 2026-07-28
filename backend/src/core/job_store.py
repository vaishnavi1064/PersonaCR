"""
Persist review job status in Redis, shaped for StatusResponse / ReportResponse.

Keys: personacr:job:{job_id}  (JSON)
Dev-scale single-worker setup — not a distributed job registry.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from backend.src.core.models import ReportResponse, StatusResponse
from backend.src.core.redis_client import get_redis

JOB_KEY_PREFIX = "personacr:job:"
JOB_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def create_job(
    job_id: str,
    *,
    message: str | None = "queued",
    meta: dict[str, Any] | None = None,
) -> StatusResponse:
    now = _now()
    payload: dict[str, Any] = {
        "job_id": job_id,
        "state": "queued",
        "progress": 0,
        "message": message,
        "result": None,
        "error": None,
        "review_id": None,
        "created_at": now,
        "updated_at": now,
        "meta": meta or {},
    }
    r = get_redis()
    r.set(_key(job_id), json.dumps(payload), ex=JOB_TTL_SECONDS)
    return StatusResponse.model_validate(payload)


def update_job(
    job_id: str,
    *,
    state: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    review_id: str | None = None,
) -> StatusResponse:
    current = get_job_dict(job_id)
    if current is None:
        raise KeyError(f"Unknown job_id: {job_id}")

    if state is not None:
        current["state"] = state
    if progress is not None:
        current["progress"] = progress
    if message is not None:
        current["message"] = message
    if result is not None:
        current["result"] = result
    if error is not None:
        current["error"] = error
    if review_id is not None:
        current["review_id"] = review_id
    current["updated_at"] = _now()

    r = get_redis()
    r.set(_key(job_id), json.dumps(current), ex=JOB_TTL_SECONDS)
    return StatusResponse.model_validate(current)


def get_job_dict(job_id: str) -> dict[str, Any] | None:
    raw = get_redis().get(_key(job_id))
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


def get_job(job_id: str) -> StatusResponse | None:
    data = get_job_dict(job_id)
    if data is None:
        return None
    return StatusResponse.model_validate(data)


def to_report_response(job: StatusResponse) -> ReportResponse | None:
    """Map a completed job onto the orphaned ReportResponse model."""
    if job.state != "completed" or job.result is None:
        return None
    return ReportResponse(
        job_id=job.job_id,
        review_id=job.review_id or job.job_id,
        status=job.state,
        report=job.result,
    )
