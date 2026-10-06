"""
Persisted repo-analysis status per (user, repo), in Redis.

Keys:
  personacr:analysis:{user_id}:{repo_hash}   JSON record (latest analysis of that repo)
  personacr:analyses:{user_id}               set of repo hashes the user has analyzed

A record survives page reloads and closed tabs (7-day TTL). GET /api/repos
merges it into the repo list, so the UI can show Analyzing / Failed without
having started the job itself. Ready comes from the saved fingerprint.

A running record whose worker stopped beating is marked failed when read
(core/liveness.py), so it neither shows "Analyzing" forever nor blocks a new run.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from backend.src.core import job_store, liveness
from backend.src.core.redis_client import get_redis

RECORD_TTL_SECONDS = 60 * 60 * 24 * 7
ACTIVE_STATES = ("queued", "running")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/").removesuffix(".git")


def _hash(repo_url: str) -> str:
    return hashlib.sha1(normalize_url(repo_url).lower().encode()).hexdigest()[:16]


def _key(user_id: str, repo_url: str) -> str:
    return f"personacr:analysis:{user_id}:{_hash(repo_url)}"


def _index(user_id: str) -> str:
    return f"personacr:analyses:{user_id}"


def _decode(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


def _reconciled(user_id: str, record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not liveness.is_stale(record):
        return record
    assert record is not None
    if record.get("job_id"):
        job_store.fail_if_active(record["job_id"], liveness.WORKER_STOPPED)
    return _failed(user_id, record, liveness.WORKER_STOPPED)


def _failed(user_id: str, record: dict[str, Any], error: str) -> dict[str, Any]:
    return put_record(user_id, record["repo_url"], {
        **record, "state": "failed", "stage": "failed", "message": "Failed", "error": error, "finished_at": _now(),
    })


def get_record(user_id: str, repo_url: str) -> dict[str, Any] | None:
    return _reconciled(user_id, _decode(get_redis().get(_key(user_id, repo_url))))


def put_record(user_id: str, repo_url: str, record: dict[str, Any]) -> dict[str, Any]:
    r = get_redis()
    record = {**record, "repo_url": normalize_url(repo_url), "updated_at": _now()}
    r.set(_key(user_id, repo_url), json.dumps(record), ex=RECORD_TTL_SECONDS)
    r.sadd(_index(user_id), _hash(repo_url))
    r.expire(_index(user_id), RECORD_TTL_SECONDS)
    return record


def start_record(user_id: str, repo_url: str, job_id: str, *, force: bool) -> dict[str, Any]:
    return put_record(user_id, repo_url, {
        "job_id": job_id,
        "state": "queued",
        "stage": "queued",
        "progress": 0,
        "message": "Waiting for a worker",
        "force": force,
        "error": None,
        "started_at": _now(),
        "finished_at": None,
        "summary": None,
    })


def update_record(
    user_id: str, repo_url: str, *, only_job_id: str | None = None, **fields: Any
) -> dict[str, Any] | None:
    """Merge fields into the record. With only_job_id, skip it if a newer job owns the record."""
    current = _decode(get_redis().get(_key(user_id, repo_url)))
    if current is None or (only_job_id is not None and current.get("job_id") != only_job_id):
        return None
    return put_record(user_id, repo_url, {**current, **fields})


def beat(user_id: str, repo_url: str, job_id: str) -> None:
    """Heartbeat: refresh updated_at while this job's analysis is running."""
    current = _decode(get_redis().get(_key(user_id, repo_url)))
    if current and current.get("job_id") == job_id and current.get("state") == "running":
        put_record(user_id, repo_url, current)


def fail_if_active(user_id: str, repo_url: str, job_id: str, error: str) -> bool:
    """Mark this job's analysis failed if it's still queued/running (RQ failure hooks)."""
    current = _decode(get_redis().get(_key(user_id, repo_url)))
    if not current or current.get("job_id") != job_id or current.get("state") not in ACTIVE_STATES:
        return False
    _failed(user_id, current, error)
    return True


def list_records(user_id: str) -> list[dict[str, Any]]:
    r = get_redis()
    hashes = [h.decode() if isinstance(h, bytes) else h for h in r.smembers(_index(user_id))]
    records: list[dict[str, Any]] = []
    for h in hashes:
        rec = _reconciled(user_id, _decode(r.get(f"personacr:analysis:{user_id}:{h}")))
        if rec is not None:
            records.append(rec)
        else:
            r.srem(_index(user_id), h)  # expired record
    return records


def public_view(record: dict[str, Any] | None) -> dict[str, Any] | None:
    """The fields the UI needs (no fingerprint payload)."""
    if record is None:
        return None
    return {k: record.get(k) for k in (
        "job_id", "state", "stage", "progress", "message", "error", "started_at", "finished_at", "force",
    )}
