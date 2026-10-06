"""
Repo-scoped chat memory for the Insights agent.

Two parts, both bounded:
  - this chat's recent turns (sent by the client), for follow-up questions;
  - the user's OTHER saved chats about the SAME repo (read here, service role):
    their latest Q&A pairs and review notes.
Never mixed across repos: a chat counts only if its repo (selected_repos[0],
else primary/last repo) is the asked-about repo, and nothing is loaded when
more than one repo is selected.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from backend.src.core.models import ChatTurn
from backend.src.core.repo_identity import as_uuid_or_none

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 8
MAX_PAST_CHATS = 3
MAX_PAST_ITEMS_PER_CHAT = 3
MAX_CHARS = 600


def _norm(url: str | None) -> str:
    return (url or "").strip().rstrip("/").removesuffix(".git").lower()


def _clip(text: str, n: int = MAX_CHARS) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def chat_repo(row: dict[str, Any]) -> str | None:
    selected = row.get("selected_repos")
    if isinstance(selected, list) and selected:
        return selected[0]
    return row.get("primary_repo_url") or row.get("last_repo_url")


# Old chats saved the UI's welcome/help line as a bot message — it isn't an answer
_UI_HINT = re.compile(r"^(paste a github repo url|select (a|at least one) repo|choose a repo)", re.I)


def _items_from_messages(messages: list[dict[str, Any]]) -> list[str]:
    """Q&A pairs and one-line review notes, oldest → newest."""
    items: list[str] = []
    pending_q: str | None = None
    for m in messages or []:
        role, mtype = m.get("role"), m.get("type") or "text"
        data = m.get("data") or {}
        content = m.get("content") or ""
        if role == "user":
            if data.get("mode") == "review":
                pending_q = None  # the review result below describes it
            elif content.strip():
                pending_q = content
        elif role == "bot" and mtype == "review":
            score = data.get("overall_score")
            issues = data.get("issues") or []
            score_txt = "no score (degraded)" if score is None else f"score {round(score)}/100"
            cats = sorted({str(i.get("category") or i.get("type")) for i in issues})[:4]
            items.append(f"Reviewed code: {score_txt}, {len(issues)} findings" + (f" ({', '.join(cats)})" if cats else ""))
        elif role == "bot" and mtype == "text" and pending_q and not data.get("error") and not _UI_HINT.match(content.strip()):
            items.append(f"Q: {_clip(pending_q, 300)}\n   A: {_clip(content)}")
            pending_q = None
    return items


def load_past_chats(db: Any, user_id: str, repo_url: str, exclude_chat_id: str | None) -> list[dict[str, Any]]:
    """[{title, updated_at, items}] for the user's other chats about this repo, newest first."""
    if as_uuid_or_none(user_id) is None:
        return []  # guests have no saved chats
    try:
        rows = db.select_many(
            "user_chats", {"user_id": user_id},
            select="id,title,messages,selected_repos,primary_repo_url,last_repo_url,updated_at",
            order="updated_at.desc", limit=50,
        )
    except Exception as e:
        logger.warning("chat memory unavailable: %s", e)
        return []
    want = _norm(repo_url)
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("id") == exclude_chat_id or _norm(chat_repo(row)) != want:
            continue
        items = _items_from_messages(row.get("messages") or [])[-MAX_PAST_ITEMS_PER_CHAT:]
        if items:
            out.append({"title": row.get("title") or "Untitled", "updated_at": row.get("updated_at"), "items": items})
        if len(out) >= MAX_PAST_CHATS:
            break
    return out


def recent_history(history: list[ChatTurn]) -> list[ChatTurn]:
    turns = [t for t in history if t.role in ("user", "assistant") and t.content.strip()]
    return turns[-MAX_HISTORY_TURNS:]


def format_memory(history: list[ChatTurn], past: list[dict[str, Any]]) -> str:
    """Prompt section; empty string when there's nothing to remember."""
    parts: list[str] = []
    if past:
        parts.append("## Earlier chats about this repo (most recent first)")
        for chat in past:
            parts.append(f"### {chat['title']} ({(chat.get('updated_at') or '')[:10]})")
            parts.extend(f"- {item}" for item in chat["items"])
    if history:
        parts.append("## Earlier in this chat")
        parts.extend(f"{'User' if t.role == 'user' else 'You'}: {_clip(t.content)}" for t in history)
    if not parts:
        return ""
    return (
        "\n\n# Conversation memory\n"
        "Use this only for continuity (what was already asked or concluded). Facts about the code "
        "must still come from the repo data above; if they conflict, trust the repo data.\n\n"
        + "\n".join(parts)
    )
