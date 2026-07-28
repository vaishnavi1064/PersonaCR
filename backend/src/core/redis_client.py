"""
Redis connection for the review job queue.

URL from REDIS_URL in backend/.env (same dotenv pattern as Supabase/GitHub).
Default: redis://localhost:6379/0 for local docker-compose Redis.
"""
from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv("backend/.env")

_redis: Any | None = None


def get_redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


def get_redis() -> Any:
    """Return a shared Redis client (injectable via set_redis for tests)."""
    global _redis
    if _redis is None:
        from redis import Redis

        # decode_responses=False — RQ job blobs expect bytes-capable Redis.
        _redis = Redis.from_url(get_redis_url())
    return _redis


def set_redis(client: Any | None) -> None:
    """Override the shared client (tests use fakeredis)."""
    global _redis
    _redis = client


def reset_redis() -> None:
    set_redis(None)
