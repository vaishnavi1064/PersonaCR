"""
Analyze repo route — triggers Layer 1 fingerprint extraction pipeline.
POST /api/analyze-repo  →  returns FingerprintResponse
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.src.core.github_ingestor import ingest_repo
from backend.src.core.pattern_extractor import extract_fingerprint
from backend.src.core.embedder import embed_and_store
from backend.src.core.cache_manager import get_cached_fingerprint, save_fingerprint
from backend.src.db.supabase_rest import SupabaseREST

router = APIRouter(prefix="/api", tags=["fingerprint"])


class AnalyzeRequest(BaseModel):
    repo_url: str
    user_id: str = "anonymous"
    github_token: str | None = None
    force_refresh: bool = False


@router.post("/analyze-repo")
def analyze_repo(payload: AnalyzeRequest) -> dict:
    """
    Build or return a coding fingerprint for a GitHub repo.

    - If the repo was analyzed before AND the commit SHA hasn't changed, returns the cached fingerprint.
    - If stale (new commits) or force_refresh=True, re-runs the full extraction.
    """
    db = SupabaseREST()
    repo_url = payload.repo_url.rstrip("/")

    # ── Check cache ──────────────────────────────────────────────────────────
    if not payload.force_refresh:
        cached = get_cached_fingerprint(db, repo_url, payload.user_id, payload.github_token)
        if cached and cached.get("_cache_status") == "fresh":
            return {
                "repo_url": repo_url,
                "repo_name": cached.get("repo_name", ""),
                "fingerprint": cached.get("fingerprint_data", {}),
                "num_functions": cached.get("num_functions", 0),
                "last_commit_sha": cached.get("last_commit_sha", ""),
                "cache_status": "fresh",
                "message": "Loaded from cache — repo unchanged since last analysis.",
            }

    # ── Run full extraction ──────────────────────────────────────────────────
    try:
        chunks, latest_sha = ingest_repo(repo_url, payload.github_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    if not chunks:
        raise HTTPException(status_code=422, detail="No code functions found in this repo.")

    # Extract fingerprint
    fingerprint = extract_fingerprint(chunks)

    # Derive repo name from URL
    repo_name = repo_url.rstrip("/").removesuffix(".git").split("/")[-1]

    # Embed and store in ChromaDB
    try:
        embed_and_store(chunks, payload.user_id, repo_name)
    except Exception as e:
        # Non-fatal — fingerprint still works, just no similarity search
        print(f"[Warning] ChromaDB embedding failed: {e}")

    # Save to Supabase
    try:
        save_fingerprint(db, repo_url, repo_name, fingerprint, latest_sha, payload.user_id)
    except Exception as e:
        print(f"[Warning] Could not save fingerprint to Supabase: {e}")

    return {
        "repo_url": repo_url,
        "repo_name": repo_name,
        "fingerprint": fingerprint,
        "num_functions": len(chunks),
        "last_commit_sha": latest_sha,
        "cache_status": "new",
        "message": f"Analyzed {len(chunks)} functions from {repo_name}.",
    }
