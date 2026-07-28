"""RQ worker process for review jobs.

Usage (after Redis is up):
  python -m backend.src.workers.worker

Single-worker local/dev scale — not a multi-node deployment.
"""
from __future__ import annotations

import logging
import sys

from redis import Redis
from rq import Queue, Worker

from backend.src.core.redis_client import get_redis_url
from backend.src.workers.review_jobs import QUEUE_NAME

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    url = get_redis_url()
    # RQ prefers undecoded bytes for its own keys; job_store uses a separate
    # decode_responses client via get_redis().
    conn = Redis.from_url(url)
    queues = [Queue(QUEUE_NAME, connection=conn)]
    logger.info("Starting RQ worker on queue=%s redis=%s", QUEUE_NAME, url)
    worker = Worker(queues, connection=conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
