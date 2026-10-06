"""RQ worker process for background jobs: reviews and repo analysis.

Usage (after Redis is up):
  python -m backend.src.workers.worker

Single-worker local/dev scale — not a multi-node deployment. On Windows (no
fork, no SIGALRM) it runs jobs in-process with a timer-based timeout.
"""
from __future__ import annotations

import logging
import os
import sys

from redis import Redis
from rq import Queue, SimpleWorker, Worker
from rq.timeouts import TimerDeathPenalty

from backend.src.core.redis_client import get_redis_url
from backend.src.workers.analyze_jobs import QUEUE_NAME as ANALYZE_QUEUE
from backend.src.workers.failures import on_work_horse_killed
from backend.src.workers.review_jobs import QUEUE_NAME as REVIEW_QUEUE

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class WindowsWorker(SimpleWorker):
    """No fork and no SIGALRM on Windows: run jobs in-process, time out with a timer thread."""

    death_penalty_class = TimerDeathPenalty


def main() -> None:
    url = get_redis_url()
    # RQ prefers undecoded bytes for its own keys; job_store uses a separate
    # decode_responses client via get_redis().
    conn = Redis.from_url(url)
    names = [REVIEW_QUEUE, ANALYZE_QUEUE]
    queues = [Queue(name, connection=conn) for name in names]
    worker_cls = WindowsWorker if os.name == "nt" else Worker
    logger.info("Starting RQ %s on queues=%s redis=%s", worker_cls.__name__, names, url)
    # RQ runs no on_failure callback when the forked job process dies (e.g. OOM);
    # this handler marks our records failed in that case.
    worker = worker_cls(queues, connection=conn, work_horse_killed_handler=on_work_horse_killed)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
