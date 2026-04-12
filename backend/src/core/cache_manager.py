"""
Cache Manager — checks Supabase for existing fingerprints before re-running extraction.
Uses the last_commit_sha to detect if a repo has new commits since last analysis.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from github import Github
from dotenv import load_dotenv

load_dotenv("backend/.env")


def _get_latest_sha(repo_url: str, github_token: str | None = None) -> str | None:
    """Fetch the latest commit SHA for the default branch of a repo."""
    try:
        token = github_token or os.getenv("GITHUB_TOKEN")
        g = Github(token) if token else Github()
        clean_url = repo_url.rstrip("/").removesuffix(".git")
        parts = clean_url.split("/")
        owner, repo_name = parts[-2], parts[-1]
        repo = g.get_repo(f"{owner}/{repo_name}")
        return repo.get_branch(repo.default_branch).commit.sha
    except Exception:
        return None


def get_cached_fingerprint(
    db,
    repo_url: str,
    user_id: str = "anonymous",
    github_token: str | None = None,
) -> dict | None:
    """
    Check Supabase for a cached fingerprint for this repo.

    Returns:
        The cached fingerprint dict if valid (not stale), else None.
        Also returns a 'stale' flag if the SHA has changed.
    """
    try:
        existing = db.select_one("fingerprints", {"repo_url": repo_url})
    except Exception:
        return None

    if not existing:
        return None

    cached_sha = existing.get("last_commit_sha")
    latest_sha = _get_latest_sha(repo_url, github_token)

    if latest_sha and cached_sha != latest_sha:
        # Repo has new commits since last analysis
        return {
            **existing,
            "_cache_status": "stale",
            "_latest_sha": latest_sha,
        }

    return {
        **existing,
        "_cache_status": "fresh",
    }


def save_fingerprint(
    db,
    repo_url: str,
    repo_name: str,
    fingerprint_data: dict,
    last_commit_sha: str,
    user_id: str = "anonymous",
    num_chunks: int | None = None,
) -> dict:
    """
    Upsert a fingerprint record in Supabase.
    If a record already exists for this repo_url, update it.
    """
    # Supabase REST API requires PostgreSQL array notation for text[] columns
    languages_list = fingerprint_data.get("languages", [])
    languages_pg = "{" + ",".join(languages_list) + "}"

    # user_id must be a valid UUID or None (column is UUID type)
    uid = user_id if (user_id and user_id != "anonymous") else None

    # num_chunks = all ingested chunks (incl. __file__ fallbacks); fingerprint total_functions excludes __file__
    stored_count = (
        num_chunks
        if num_chunks is not None
        else fingerprint_data.get("total_functions", 0)
    )

    payload = {
        "user_id": uid,
        "repo_url": repo_url,
        "repo_name": repo_name,
        "fingerprint_data": fingerprint_data,
        "num_functions": stored_count,
        "languages": languages_pg,
        "last_commit_sha": last_commit_sha,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Check if record exists first
    existing = db.select_one("fingerprints", {"repo_url": repo_url})
    if existing:
        return db.update("fingerprints", existing["id"], payload)
    else:
        return db.insert("fingerprints", payload)
