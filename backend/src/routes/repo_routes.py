"""
Repo list route — the user's imported repos joined with their cached fingerprints
and their latest background-analysis status.
GET /api/repos?user_id=...  →  {"repos": [...]}, most recently analyzed first

Reads with the service role so the browser never needs direct access to the
`fingerprints` table. `user_id` is trusted from the query string for now, like
every other route; the backend-auth slice replaces it with the JWT subject.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from backend.src.core import analysis_store
from backend.src.core.repo_identity import as_uuid_or_none
from backend.src.db.supabase_rest import SupabaseREST

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["repos"])

_FINGERPRINT_COLUMNS = "repo_url,fingerprint_data,num_functions,languages,last_commit_sha,updated_at"


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").removesuffix(".git")


def _full_name(url: str) -> str:
    return "/".join(url.split("/")[-2:])


def _analysis_records(user_id: str) -> dict[str, dict[str, Any]]:
    """Latest analysis per repo; empty when Redis is unavailable (list still works)."""
    try:
        return {_normalize_url(r["repo_url"]): r for r in analysis_store.list_records(user_id)}
    except Exception as e:
        logger.warning("list_repos: analysis status unavailable: %s", e)
        return {}


def _item_from_record(url: str, rec: dict[str, Any]) -> dict[str, Any]:
    """A repo known only from its analysis (first import in progress/failed, or a guest's)."""
    summary = rec.get("summary") or {}
    fp = summary.get("fingerprint")
    return {
        "repo_url": url,
        "repo_name": _full_name(url),
        "languages": list(((fp or {}).get("language_distribution") or {}).keys()),
        "functions_count": summary.get("num_functions"),
        "analyzed_at": summary.get("analyzed_at"),
        "last_commit_sha": summary.get("last_commit_sha"),
        "fingerprint": fp,
        "analysis": analysis_store.public_view(rec),
    }


@router.get("/repos", operation_id="list_repos")
def list_repos(user_id: str) -> dict:
    """
    List the repos a user has imported, each with its fingerprint (or null if
    none is cached) and `analysis` (latest background analysis, or null).
    Guests get the repos analyzed in their session; "anonymous" gets none.
    """
    records = _analysis_records(user_id) if user_id.startswith("guest_") or as_uuid_or_none(user_id) else {}

    if as_uuid_or_none(user_id) is None:
        # Guests have no saved list or saved fingerprints — only their analysis records
        return {"repos": [_item_from_record(url, rec) for url, rec in records.items()]}

    db = SupabaseREST()
    try:
        rows = db.select_many(
            "user_repos", {"user_id": user_id}, order="analyzed_at.desc", limit=500
        )
    except httpx.HTTPError:
        logger.exception("list_repos: user_repos query failed")
        raise HTTPException(status_code=502, detail="Could not load your repos from the database.")

    # user_repos is append-only (one row per analyze) — keep the newest per repo.
    latest: dict[str, dict] = {}
    for row in rows:
        url = _normalize_url(row.get("repo_url") or "")
        if url and url not in latest:
            latest[url] = row

    fingerprints: dict[str, dict] = {}
    if latest:
        quoted = ",".join('"' + url.replace('"', "") + '"' for url in latest)
        try:
            fp_rows = db.select_raw(
                "fingerprints",
                {"select": _FINGERPRINT_COLUMNS, "repo_url": f"in.({quoted})"},
            )
        except httpx.HTTPError:
            logger.exception("list_repos: fingerprints query failed")
            raise HTTPException(status_code=502, detail="Could not load fingerprints from the database.")
        for fp_row in fp_rows:
            fingerprints[_normalize_url(fp_row.get("repo_url") or "")] = fp_row

    repos = []
    for url, row in latest.items():
        fp = fingerprints.get(url)
        repos.append({
            "repo_url": url,
            "repo_name": _full_name(url),
            "languages": row.get("languages") or (fp or {}).get("languages") or [],
            "functions_count": (fp or {}).get("num_functions", row.get("functions_count")),
            "analyzed_at": (fp or {}).get("updated_at") or row.get("analyzed_at"),
            "last_commit_sha": (fp or {}).get("last_commit_sha"),
            "fingerprint": (fp or {}).get("fingerprint_data"),
            "analysis": analysis_store.public_view(records.get(url)),
        })
    # Repos whose first analysis hasn't produced a user_repos row (queued, running or failed)
    for url, rec in records.items():
        if url not in latest:
            repos.insert(0, _item_from_record(url, rec))
    return {"repos": repos}
