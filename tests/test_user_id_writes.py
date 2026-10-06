"""
The backend writes with the service role, which bypasses RLS — so SupabaseREST
itself refuses any user_reviews / user_repos / user_chats write whose user_id
isn't a Supabase auth uuid (guest_<sub>, "anonymous", …) — before any request.
(user_reviews / user_repos were text columns until migration 009.)
"""
from __future__ import annotations

import pytest

from backend.src.db import supabase_rest
from backend.src.db.supabase_rest import USER_TABLES, SupabaseREST

UID = "3f2b8c1e-9a4d-4e57-8b1a-2c6d9e0f1a2b"


class _Resp:
    def raise_for_status(self) -> None: ...
    def json(self) -> list:
        return [{"ok": True}]


@pytest.fixture
def sent(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://testproj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    calls: list[tuple[str, dict]] = []

    def record(method):
        def _send(url, *, json=None, **kw):
            calls.append((method, json))
            return _Resp()
        return _send

    monkeypatch.setattr(supabase_rest.httpx, "post", record("post"))
    monkeypatch.setattr(supabase_rest.httpx, "patch", record("patch"))
    return calls


@pytest.mark.parametrize("table", sorted(USER_TABLES))
@pytest.mark.parametrize("bad", [f"guest_{UID}", "anonymous", "", None, "not-a-uuid"])
def test_non_uuid_user_ids_are_refused_before_any_request(sent, table, bad):
    db = SupabaseREST()
    with pytest.raises(ValueError, match="not a Supabase user uuid"):
        db.insert(table, {"user_id": bad, "repo_url": "https://github.com/a/b"})
    with pytest.raises(ValueError):
        db.upsert(table, {"user_id": bad, "repo_url": "https://github.com/a/b"})
    with pytest.raises(ValueError):
        db.update(table, "row-1", {"user_id": bad})
    assert sent == []


@pytest.mark.parametrize("table", sorted(USER_TABLES))
def test_missing_user_id_on_insert_is_refused(sent, table):
    with pytest.raises(ValueError):
        SupabaseREST().insert(table, {"repo_url": "https://github.com/a/b"})
    assert sent == []


def test_uuid_is_written_lowercase_to_match_auth_uid_text(sent):
    SupabaseREST().insert("user_repos", {"user_id": UID.upper(), "repo_url": "https://github.com/a/b"})
    assert sent == [("post", {"user_id": UID, "repo_url": "https://github.com/a/b"})]


def test_updates_without_user_id_and_other_tables_are_untouched(sent):
    db = SupabaseREST()
    db.update("user_chats", "row-1", {"title": "renamed"})
    db.insert("fingerprints", {"user_id": None, "repo_url": "https://github.com/a/b"})  # NULL = anonymous, by design
    assert [m for m, _ in sent] == ["patch", "post"]


def test_analyze_worker_skips_guests_and_normalizes_accounts(monkeypatch):
    from backend.src.workers import analyze_jobs

    rows: list[tuple[str, dict]] = []

    class DB:
        def insert(self, table, payload):
            rows.append((table, payload))

    monkeypatch.setattr(analyze_jobs, "SupabaseREST", DB)
    result = {"repo_url": "https://github.com/acme/api", "num_functions": 3, "fingerprint": {}}
    analyze_jobs._record_user_repo(f"guest_{UID}", result)
    analyze_jobs._record_user_repo(UID.upper(), result)
    assert [(t, p["user_id"]) for t, p in rows] == [("user_repos", UID)]


def test_guest_review_history_lookup_skips_the_db():
    """user_reviews.user_id is uuid: a guest_<sub> filter would 400, so it's never sent."""
    from backend.src.agents import insights_agent

    class NoDB:
        def select_many(self, *a, **k):
            raise AssertionError("must not query user_reviews for a guest")

    assert insights_agent._load_recent_reviews(NoDB(), "https://github.com/acme/api", f"guest_{UID}") == []
