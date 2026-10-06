"""
RQ failure hooks: mark our job/analysis records failed when RQ knows a job died.

- on_job_failure — the job's on_failure Callback. RQ calls it when the job
  raises (our jobs record their own failure first, so it's a no-op then) and
  when a restarted worker finds the job abandoned (AbandonedJobError).
- on_work_horse_killed — the Worker's work_horse_killed_handler. RQ marks the
  job failed when the forked process dies (e.g. OOM-killed) but runs no
  on_failure callback for it, so this covers that case.

Both only touch records that are still queued/running and still belong to
this job. Anything RQ can't see (the whole pod killed) is caught by the
heartbeat staleness check in core/liveness.py.
"""
from __future__ import annotations

import logging
from typing import Any

from rq.exceptions import AbandonedJobError

from backend.src.core import analysis_store, job_store, liveness

logger = logging.getLogger(__name__)


def _mark_failed(rq_job: Any, error: str) -> None:
    args = list(getattr(rq_job, "args", None) or [])
    if not args:
        return
    job_id = args[0]
    payload = args[1] if len(args) > 1 and isinstance(args[1], dict) else {}
    try:
        changed = job_store.fail_if_active(job_id, error)
        if payload.get("user_id") and payload.get("repo_url"):  # analyze job
            changed = analysis_store.fail_if_active(payload["user_id"], payload["repo_url"], job_id, error) or changed
        if changed:
            logger.warning("Marked job %s failed: %s", job_id, error)
    except Exception:
        logger.exception("Could not mark job %s failed", job_id)


def on_job_failure(job: Any, connection: Any, exc_type: Any, exc_value: Any, tb: Any) -> None:
    if exc_type is AbandonedJobError or isinstance(exc_value, AbandonedJobError):
        _mark_failed(job, liveness.WORKER_STOPPED)
    else:
        _mark_failed(job, f"Failed: {exc_value}")


def on_work_horse_killed(job: Any, retpid: int, ret_val: int, rusage: Any) -> None:
    _mark_failed(job, liveness.WORKER_KILLED)
