"""
Liveness for background jobs (analyze + review).

A job that is "running" but whose worker died (pod restart, crash, OOM) would
otherwise stay "running" until its record expires — and a running analysis
blocks new ones for that repo. So:

- A running job beats: Heartbeat (below) touches its records every
  HEARTBEAT_SECONDS from a thread, independent of stage progress (embedding a
  big repo reports no progress for minutes).
- A reader treats a running record with no heartbeat or progress for
  STALE_AFTER_SECONDS as dead and marks it failed (job_store / analysis_store
  do this on read), so the UI shows Failed + retry and Reanalyze starts fresh.
- RQ's failure hooks (workers/failures.py) mark it failed sooner where RQ can
  tell: the job process was killed, or a restarted worker finds it abandoned.

"queued" never goes stale here — a queued job is waiting for a worker, which
the UI already explains.
"""
from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 15.0
STALE_AFTER_SECONDS = float(os.getenv("JOB_STALE_SECONDS", "120"))

WORKER_STOPPED = "The background worker stopped while this was running (restart or crash). Try again."
WORKER_KILLED = "The background worker process was killed while this was running (possibly out of memory). Try again."


def _parse(ts: Any) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_stale(doc: dict[str, Any] | None, now: datetime | None = None) -> bool:
    """Running, and nothing (heartbeat or progress) written for STALE_AFTER_SECONDS."""
    if not doc or doc.get("state") != "running":
        return False
    last = _parse(doc.get("updated_at")) or _parse(doc.get("started_at")) or _parse(doc.get("created_at"))
    if last is None:
        return False
    return ((now or datetime.now(timezone.utc)) - last).total_seconds() > STALE_AFTER_SECONDS


class Heartbeat:
    """Context manager: call beat() every `interval` seconds on a daemon thread until exit."""

    def __init__(self, beat: Callable[[], None], interval: float | None = None) -> None:
        self._beat = beat
        self._interval = HEARTBEAT_SECONDS if interval is None else interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="job-heartbeat", daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._beat()
            except Exception:  # a missed beat must never fail the job
                logger.warning("Job heartbeat failed", exc_info=True)

    def __enter__(self) -> "Heartbeat":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
