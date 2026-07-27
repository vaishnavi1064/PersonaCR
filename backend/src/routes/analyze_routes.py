"""
Analyze repo route — triggers Layer 1 fingerprint extraction pipeline.
POST /api/analyze-repo  →  returns FingerprintResponse
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.src.core.github_ingestor import ingest_repo
from backend.src.core.pattern_extractor import extract_fingerprint
from backend.src.core.embedder import embed_and_store, delete_guest_collections
from backend.src.core.cache_manager import get_cached_fingerprint, save_fingerprint
from backend.src.db.supabase_rest import SupabaseREST

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["fingerprint"])


class AnalyzeRequest(BaseModel):
    repo_url: str
    user_id: str = "anonymous"
    github_token: str | None = None
    force_refresh: bool = False


@router.post("/analyze-repo", operation_id="analyze_repo")
def analyze_repo(payload: AnalyzeRequest) -> dict:
    """
    Analyze a GitHub repository to build a developer's coding fingerprint.

    Extracts 30+ code features including function length, error handling rate,
    naming conventions, docstring coverage, comment density, complexity metrics,
    and indentation style. Stores code embeddings in ChromaDB for similarity
    search during reviews. Caches the fingerprint in Supabase keyed to the
    latest commit SHA — repeated calls are instant if the repo hasn't changed.

    Must be called before review_code — the fingerprint is required for
    personalized review. Use force_refresh=true to re-analyze after new commits.
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
                "embedding": {
                    "status": "cached",
                    "collection": None,
                    "chunks_embedded": 0,
                    "error": None,
                },
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

    # Embed and store in ChromaDB (explicit status — never silent)
    embedding_info: dict = {
        "status": "skipped",
        "collection": None,
        "chunks_embedded": 0,
        "error": None,
    }
    try:
        emb = embed_and_store(chunks, payload.user_id, repo_name)
        embedding_info = {
            "status": "ok",
            "collection": emb.get("collection"),
            "chunks_embedded": emb.get("chunks_embedded", 0),
            "error": None,
        }
    except Exception as e:
        logger.exception("ChromaDB embedding failed for %s", repo_url)
        embedding_info = {
            "status": "failed",
            "collection": None,
            "chunks_embedded": 0,
            "error": str(e),
        }

    # Save to Supabase — skip for guest sessions (no persistent account)
    is_guest = payload.user_id.startswith("guest_")
    if not is_guest:
        try:
            save_fingerprint(
                db,
                repo_url,
                repo_name,
                fingerprint,
                latest_sha,
                payload.user_id,
                num_chunks=len(chunks),
            )
        except Exception as e:
            logger.warning("Could not save fingerprint to Supabase: %s", e)

    return {
        "repo_url": repo_url,
        "repo_name": repo_name,
        "fingerprint": fingerprint,
        "num_functions": len(chunks),
        "last_commit_sha": latest_sha,
        "cache_status": "new",
        "message": f"Analyzed {len(chunks)} functions from {repo_name}.",
        "embedding": embedding_info,
    }


@router.delete("/cleanup-guest/{session_id}", operation_id="cleanup_guest")
def cleanup_guest(session_id: str) -> dict:
    """
    Wipe all ChromaDB collections for a guest session.
    Called via sendBeacon when the guest closes their tab.
    """
    if not session_id.startswith("guest_"):
        return {"deleted": 0, "message": "Not a guest session — nothing to do."}
    deleted = delete_guest_collections(session_id)
    logger.info("Cleaned up %d guest collections for %s", deleted, session_id)
    return {"deleted": deleted, "message": f"Removed {deleted} collection(s) for guest session."}
