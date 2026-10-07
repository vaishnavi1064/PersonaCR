"""
Chat route — POST /api/chat

Handles free-form conversational Q&A by routing to the Insights Agent.
The agent answers questions grounded in the user's fingerprints, reviews,
and code embeddings — read-only, no side effects.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.src.core import rate_limit
from backend.src.core.auth import AuthUser, current_user
from backend.src.core.models import InsightsChatRequest, InsightsChatResponse
from backend.src.agents.insights_agent import get_insights

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", operation_id="ask_insights")
def ask_insights(payload: InsightsChatRequest, user: AuthUser = Depends(current_user)) -> InsightsChatResponse:
    """
    Ask a natural-language question about your analyzed repositories.

    Retrieves the developer's coding fingerprint, recent review history,
    and optionally similar code snippets from ChromaDB to ground the
    answer in real data. The agent will never fabricate information —
    if the data doesn't contain the answer, it says so.

    Requires at least one selected_repo_url that has been previously
    analyzed via POST /api/analyze-repo.
    """
    if not payload.selected_repo_urls:
        raise HTTPException(
            status_code=400,
            detail="At least one repo URL must be selected to ask questions.",
        )

    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    rate_limit.enforce(user.user_id, rate_limit.CHAT)

    logger.info(
        "Chat request from user=%s with %d repo(s): %s",
        user.user_id,
        len(payload.selected_repo_urls),
        payload.message[:80],
    )

    try:
        result = get_insights(
            question=payload.message,
            selected_repo_urls=payload.selected_repo_urls,
            user_id=user.user_id,
            history=payload.history,
            chat_id=payload.chat_id,
        )
    except Exception as e:
        logger.exception("Insights agent failed")
        raise HTTPException(status_code=500, detail=f"Insights agent error: {e}")

    return InsightsChatResponse(
        answer=result.answer,
        repos_used=result.repos_used,
        code_chunks_retrieved=result.code_chunks_retrieved,
        memory=result.memory,
        error=result.error,
    )
