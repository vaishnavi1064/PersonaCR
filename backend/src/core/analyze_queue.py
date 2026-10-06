"""Enqueue helpers for the analyze RQ queue."""
from __future__ import annotations

from typing import Any

from rq import Callback, Queue

from backend.src.core.redis_client import get_redis
from backend.src.workers.failures import on_job_failure
from backend.src.workers.analyze_jobs import JOB_TIMEOUT_SECONDS, QUEUE_NAME, process_analyze_job


def get_analyze_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=get_redis())


def enqueue_analyze_job(job_id: str, payload: dict[str, Any]) -> str:
    rq_job = get_analyze_queue().enqueue(
        process_analyze_job,
        job_id,
        payload,
        job_id=job_id,
        job_timeout=JOB_TIMEOUT_SECONDS,
        result_ttl=86400,
        failure_ttl=86400,
        on_failure=Callback(on_job_failure),
    )
    return rq_job.id
