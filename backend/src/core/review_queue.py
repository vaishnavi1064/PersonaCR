"""Enqueue helpers for the reviews RQ queue."""
from __future__ import annotations

from typing import Any

from rq import Queue

from backend.src.core.redis_client import get_redis
from backend.src.workers.review_jobs import QUEUE_NAME, process_review_job


def get_reviews_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=get_redis())


def enqueue_review_job(job_id: str, payload: dict[str, Any]) -> str:
    """Enqueue process_review_job; returns the RQ job id (same as our job_id)."""
    q = get_reviews_queue()
    rq_job = q.enqueue(
        process_review_job,
        job_id,
        payload,
        job_id=job_id,
        result_ttl=86400,
        failure_ttl=86400,
    )
    return rq_job.id
