"""
Repo identity — the single key for per-repo data.

Fingerprints are looked up by repo_url, and Chroma collections are named from
(owner, repo_name) parsed from that same URL. Who requested an analyze or
review (a Supabase UUID, a guest_ session, or "anonymous") never changes which
collection a repo uses, so analyze-as-A / review-as-B hit the same vectors.
"""
from __future__ import annotations

import uuid


def repo_identity(repo_url: str) -> tuple[str, str]:
    """
    Return (owner, repo_name) for https://github.com/<owner>/<repo>[.git][/].

    owner is the Chroma collection namespace for app traffic (embedder's
    ``user_id`` argument); repo_name is the repo segment without ``.git``.
    """
    parts = repo_url.rstrip("/").removesuffix(".git").split("/")
    if len(parts) < 2 or not parts[-1] or not parts[-2]:
        raise ValueError(f"Invalid repo URL — expected https://github.com/owner/repo, got {repo_url!r}")
    return parts[-2], parts[-1]


def as_uuid_or_none(value: str | None) -> str | None:
    """Return value if it is a valid UUID (Supabase auth user id), else None."""
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None
