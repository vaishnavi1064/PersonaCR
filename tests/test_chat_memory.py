"""Repo-scoped chat memory: this chat's turns + earlier chats about the SAME repo only. LLM mocked."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.src.agents import insights_agent as ia
from backend.src.core import chat_memory as cm
from backend.src.core.models import ChatTurn

USER = "3f2b8c1e-9a4d-4e57-8b1a-2c6d9e0f1a2b"
API = "https://github.com/acme/api"
WEB = "https://github.com/acme/web"


def chat(id_, repo, messages, title="t", updated="2026-10-0"):
    return {"id": id_, "title": title, "selected_repos": [repo] if repo else [], "primary_repo_url": None,
            "last_repo_url": None, "updated_at": updated, "messages": messages}


def qa(q, a):
    return [
        {"role": "user", "type": "text", "content": q, "data": {"mode": "ask"}},
        {"role": "bot", "type": "text", "content": a, "data": {}},
    ]


ROWS = [
    chat("current", API, qa("current question", "current answer"), updated="2026-10-06"),
    chat("c1", API, qa("How do we name handlers?", "snake_case, e.g. handle_order.")
         + [{"role": "user", "type": "text", "content": "def x(): pass", "data": {"mode": "review"}},
            {"role": "bot", "type": "review", "content": None,
             "data": {"overall_score": 72.4, "issues": [{"category": "naming"}, {"category": "bug"}]}}],
         title="Naming", updated="2026-10-05"),
    chat("w1", WEB, qa("WEB SECRET QUESTION", "web answer"), title="Web chat", updated="2026-10-04"),
    chat("c2", API, qa("Error handling?", "Mostly try/except around IO.")
         + [{"role": "user", "type": "text", "content": "and retries?", "data": {"mode": "ask"}},
            {"role": "bot", "type": "text", "content": "Error: failed", "data": {"error": True}}],
         title="Errors", updated="2026-10-03"),
    {**chat("legacy", None, qa("legacy multi-repo q", "legacy a"), updated="2026-10-02"),
     "selected_repos": [WEB, API]},  # older multi-repo chat: its repo is selected_repos[0] = WEB
]


@pytest.fixture
def db():
    d = MagicMock()
    d.select_many.return_value = ROWS
    return d


# ── load_past_chats ───────────────────────────────────────────────────────────

def test_only_same_repo_chats_never_other_repos(db):
    past = cm.load_past_chats(db, USER, API + "/", exclude_chat_id="current")
    assert [c["title"] for c in past] == ["Naming", "Errors"]
    text = repr(past)
    assert "WEB SECRET QUESTION" not in text and "legacy multi-repo q" not in text
    assert "current question" not in text  # the current chat comes from history, not the DB


def test_items_are_qa_pairs_and_review_notes_errors_skipped(db):
    naming, errors = cm.load_past_chats(db, USER, API, "current")
    assert naming["items"][0].startswith("Q: How do we name handlers?")
    assert naming["items"][1] == "Reviewed code: score 72/100, 2 findings (bug, naming)"
    assert errors["items"] == ["Q: Error handling?\n   A: Mostly try/except around IO."]  # failed answer dropped


def test_guest_and_bounded(db):
    assert cm.load_past_chats(db, "guest_x", API, None) == []
    many = [chat(f"c{i}", API, qa(f"q{i}", "a" * 5000) * 10) for i in range(10)]
    db.select_many.return_value = many
    past = cm.load_past_chats(db, USER, API, None)
    assert len(past) == cm.MAX_PAST_CHATS
    assert all(len(c["items"]) <= cm.MAX_PAST_ITEMS_PER_CHAT for c in past)
    assert all(len(item) < 1000 for c in past for item in c["items"])


def test_db_failure_means_no_memory_not_an_error(db):
    db.select_many.side_effect = RuntimeError("down")
    assert cm.load_past_chats(db, USER, API, None) == []


def test_history_is_bounded_and_formatted():
    turns = [ChatTurn(role="user" if i % 2 == 0 else "assistant", content=f"m{i}") for i in range(20)]
    recent = cm.recent_history(turns)
    assert len(recent) == cm.MAX_HISTORY_TURNS and recent[-1].content == "m19"
    text = cm.format_memory(recent, [])
    assert "Earlier in this chat" in text and "User: m12" in text and "You: m13" in text
    assert "trust the repo data" in text
    assert cm.format_memory([], []) == ""


# ── get_insights / route ──────────────────────────────────────────────────────

@pytest.fixture
def insights(monkeypatch, db):
    monkeypatch.setattr(ia, "SupabaseREST", lambda: db)
    monkeypatch.setattr(ia, "_load_fingerprint", lambda d, url: {"fingerprint_data": {"naming_convention": "snake_case"}, "languages": ["python"], "num_functions": 3})
    monkeypatch.setattr(ia, "_load_recent_reviews", lambda *a, **k: [])
    monkeypatch.setattr(ia, "_retrieve_code_snippets", lambda *a, **k: [])
    prompts: list[str] = []

    def fake_complete(system, user, **kw):
        prompts.append(system)
        return "Answer."

    monkeypatch.setattr("backend.src.core.llm_client.complete", fake_complete)
    return prompts


def test_prompt_contains_this_repos_memory_only(insights):
    out = ia.get_insights("And for handlers?", [API], USER,
                          history=[ChatTurn(role="user", content="How do we name things?"), ChatTurn(role="assistant", content="snake_case.")],
                          chat_id="current")
    prompt = insights[0]
    assert "How do we name handlers?" in prompt and "Mostly try/except" in prompt
    assert "User: How do we name things?" in prompt
    assert "WEB SECRET QUESTION" not in prompt and "legacy multi-repo q" not in prompt
    assert out.memory.model_dump() == {"current_turns": 2, "past_chats": 2, "past_turns": 3}
    assert out.error is None


def test_two_repos_selected_means_no_past_chats(insights):
    out = ia.get_insights("Compare", [API, WEB], USER, history=[], chat_id=None)
    assert out.memory.past_chats == 0
    assert "Earlier chats about this repo" not in insights[0]


def test_llm_failure_is_flagged_not_a_fake_answer(insights, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("backend.src.core.llm_client.complete", boom)
    out = ia.get_insights("q", [API], USER)
    assert out.answer == "" and "model call failed" in out.error


def test_route_passes_history_and_returns_memory(insights):
    from backend.src.main import app

    with TestClient(app) as c:
        res = c.post("/api/chat", json={
            "message": "follow-up", "selected_repo_urls": [API], "user_id": USER, "chat_id": "current",
            "history": [{"role": "user", "content": "first q"}, {"role": "assistant", "content": "first a"}],
        })
    body = res.json()
    assert res.status_code == 200 and body["answer"] == "Answer."
    assert body["memory"] == {"current_turns": 2, "past_chats": 2, "past_turns": 3}
    assert body["error"] is None
    assert "User: first q" in insights[0]


def test_legacy_ui_hints_are_not_remembered_as_answers(db):
    db.select_many.return_value = [chat("old", API, qa("hey", "Paste a GitHub repo URL to analyze, or paste code to review."))]
    assert cm.load_past_chats(db, USER, API, None) == []
