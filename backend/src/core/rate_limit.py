"""
Per-user rate limits on the endpoints that cost money (LLM calls) or CPU (repo
analysis) — abuse protection for the public demo.

Sliding window in Redis: one sorted set per (action, user), scored by request
time. A request is added, counted, and removed again if it went over the limit,
all in one MULTI so two concurrent requests can't both slip through.

A global per-day cap per action backs this up: guests are Supabase anonymous
sign-ins, so a determined caller can mint new user ids; the global cap bounds
the total spend no matter how many ids there are.

Configuration (env, read per request so tests and ops can change it):
  RATE_LIMIT_ENABLED            1 (default) / 0
  RATE_LIMIT_REVIEWS_PER_HOUR   per user, default 5   (POST /api/review, /api/reviews)
  RATE_LIMIT_CHATS_PER_HOUR     per user, default 30  (POST /api/chat)
  RATE_LIMIT_ANALYZES_PER_HOUR  per user, default 5   (POST /api/analyze-repo, /api/analyze-jobs)
  RATE_LIMIT_REVIEWS_PER_DAY    all users, default 300; 0 = no global cap
  RATE_LIMIT_CHATS_PER_DAY      all users, default 1000
  RATE_LIMIT_ANALYZES_PER_DAY   all users, default 100
  RATE_LIMIT_EXEMPT_USERS       comma-separated user ids (account uuids) never limited

If Redis is unreachable the request is allowed (logged): the queue-backed
routes fail on their own with a 503, and chat shouldn't go down with Redis.
"""
from __future__ import annotations

import logging
import math
import os
import time
import uuid
from dataclasses import dataclass

from fastapi import HTTPException

from backend.src.core.redis_client import get_redis

logger = logging.getLogger(__name__)

HOUR = 3600
DAY = 86400


@dataclass(frozen=True)
class Action:
    name: str
    noun: str      # for messages: "reviews", "questions", "repo analyses"
    noun_one: str  # "review" — when the limit is 1
    hourly_env: str
    hourly_default: int
    daily_env: str
    daily_default: int


REVIEW = Action("review", "reviews", "review", "RATE_LIMIT_REVIEWS_PER_HOUR", 5, "RATE_LIMIT_REVIEWS_PER_DAY", 300)
CHAT = Action("chat", "questions", "question", "RATE_LIMIT_CHATS_PER_HOUR", 30, "RATE_LIMIT_CHATS_PER_DAY", 1000)
ANALYZE = Action("analyze", "repo analyses", "repo analysis", "RATE_LIMIT_ANALYZES_PER_HOUR", 5, "RATE_LIMIT_ANALYZES_PER_DAY", 100)


def _enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(int(raw), 0)
    except ValueError:
        logger.warning("%s=%r is not an integer; using %d", name, raw, default)
        return default


def _exempt(user_id: str) -> bool:
    exempt = {u.strip() for u in os.getenv("RATE_LIMIT_EXEMPT_USERS", "").split(",") if u.strip()}
    return user_id in exempt


def _wait_text(seconds: int) -> str:
    minutes = max(1, math.ceil(seconds / 60))
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = math.ceil(minutes / 60)
    return f"{hours} hour{'s' if hours != 1 else ''}"


def _take(key: str, limit: int, window: int, now: float) -> tuple[bool, int, str]:
    """
    Record one request under `key`; return (allowed, retry_after_seconds, member).
    Over the limit, the request is removed again so rejected calls don't extend the wait.
    """
    redis = get_redis()
    member = f"{now:.6f}:{uuid.uuid4().hex}"
    pipe = redis.pipeline(transaction=True)
    pipe.zremrangebyscore(key, 0, now - window)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window)
    _, _, count, _ = pipe.execute()
    if count <= limit:
        return True, 0, member
    redis.zrem(key, member)
    oldest = redis.zrange(key, 0, 0, withscores=True)
    retry = int(math.ceil(oldest[0][1] + window - now)) if oldest else window
    return False, max(retry, 1), member


def enforce(user_id: str, action: Action) -> None:
    """Count one `action` by `user_id`; raise HTTP 429 (with Retry-After) if over a limit."""
    if not _enabled() or _exempt(user_id):
        return
    hourly = _int_env(action.hourly_env, action.hourly_default)
    daily = _int_env(action.daily_env, action.daily_default)
    now = time.time()
    user_key = f"ratelimit:{action.name}:user:{user_id}"
    member = ""
    try:
        if hourly:
            ok, retry, member = _take(user_key, hourly, HOUR, now)
            if not ok:
                logger.info("Rate limit: user=%s action=%s (%d/hour)", user_id, action.name, hourly)
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"You've reached the demo limit of {hourly} "
                        f"{action.noun if hourly != 1 else action.noun_one} per hour. "
                        f"Try again in {_wait_text(retry)}."
                    ),
                    headers={"Retry-After": str(retry)},
                )
        if daily:
            ok, retry, _ = _take(f"ratelimit:{action.name}:global", daily, DAY, now)
            if not ok:
                if member:
                    get_redis().zrem(user_key, member)  # not the caller's fault — don't count it
                logger.warning("Global rate limit reached: action=%s (%d/day)", action.name, daily)
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"The public demo has used up today's {action.noun}. "
                        f"Try again in {_wait_text(retry)}."
                    ),
                    headers={"Retry-After": str(retry)},
                )
    except HTTPException:
        raise
    except Exception as e:  # Redis down — allow (see module docstring)
        logger.warning("Rate limiter unavailable (%s); allowing %s for %s", e, action.name, user_id)
