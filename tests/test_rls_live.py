"""
Live RLS check against the real Supabase project — run after applying
migrations/007 and 008:

    PERSONACR_RLS_LIVE=1 pytest -m integration tests/test_rls_live.py -v

Uses only the public anon key (SUPABASE_ANON_KEY, else VITE_SUPABASE_ANON_KEY
from frontend/.env), exactly what a browser has:
  1. The bare anon key (no user session) reads nothing from any table.
  2. Two anonymous sign-ins, A and B: A's rows are invisible to B, and B can't
     update, delete, or forge rows as A — while A still reads its own rows.

Needs "Allow anonymous sign-ins" on (part 2 skips otherwise). The two test users
are deleted afterwards when SUPABASE_SERVICE_ROLE_KEY is available.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("PERSONACR_RLS_LIVE") != "1", reason="live Supabase check; set PERSONACR_RLS_LIVE=1"),
]

URL = os.getenv("SUPABASE_URL", "").rstrip("/")
ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or dotenv_values(ROOT / "frontend" / ".env").get("VITE_SUPABASE_ANON_KEY") or ""
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Minimal row per table, and a column change B will try on A's row
USER_TABLES = {
    "user_chats": {"title": "rls-live-test"},
    "user_repos": {"repo_url": "https://github.com/rls-live/test"},
    "user_reviews": {"repo_url": "https://github.com/rls-live/test"},
}
TAMPER = {"user_chats": {"title": "pwned"}, "user_repos": {"repo_name": "pwned"}, "user_reviews": {"repo_name": "pwned"}}


def _headers(token: str) -> dict[str, str]:
    return {"apikey": ANON_KEY, "Authorization": f"Bearer {token}", "Content-Type": "application/json",
            "Prefer": "return=representation"}


def _rest(table: str) -> str:
    return f"{URL}/rest/v1/{table}"


@pytest.fixture(scope="module", autouse=True)
def _configured() -> None:
    if not URL or not ANON_KEY:
        pytest.fail("SUPABASE_URL and an anon key (SUPABASE_ANON_KEY or VITE_SUPABASE_ANON_KEY) are required")


def _denied_or_empty(res: httpx.Response) -> bool:
    # Revoked table → 401/403 (permission denied); RLS with no matching policy → 200 [].
    return res.status_code in (401, 403) or (res.status_code == 200 and res.json() == [])


@pytest.mark.parametrize("table", [*USER_TABLES, "fingerprints"])
def test_bare_anon_key_reads_nothing(table):
    res = httpx.get(_rest(table), params={"select": "*", "limit": "5"}, headers=_headers(ANON_KEY), timeout=20)
    assert _denied_or_empty(res), f"anon key read {table}: {res.status_code} {res.text[:200]}"


@pytest.mark.parametrize("table", list(USER_TABLES))
def test_bare_anon_key_cannot_write(table):
    row = {"user_id": str(uuid.uuid4()), **USER_TABLES[table]}
    res = httpx.post(_rest(table), json=row, headers=_headers(ANON_KEY), timeout=20)
    assert res.status_code in (401, 403), f"anon key wrote {table}: {res.status_code} {res.text[:200]}"


def _anonymous_sign_in() -> tuple[str, str]:
    res = httpx.post(f"{URL}/auth/v1/signup", json={}, headers={"apikey": ANON_KEY}, timeout=20)
    if res.status_code != 200 or "access_token" not in res.json():
        pytest.skip(f"anonymous sign-in unavailable ({res.status_code}: {res.text[:120]}) — enable it to run this check")
    body = res.json()
    return body["user"]["id"], body["access_token"]


@pytest.fixture(scope="module")
def two_users() -> Iterator[tuple[tuple[str, str], tuple[str, str]]]:
    a, b = _anonymous_sign_in(), _anonymous_sign_in()
    yield a, b
    if SERVICE_KEY:  # test rows are removed per test; this removes the two auth users
        for uid, _ in (a, b):
            httpx.delete(f"{URL}/auth/v1/admin/users/{uid}",
                         headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}, timeout=20)


@pytest.mark.parametrize("table", list(USER_TABLES))
def test_users_cannot_touch_each_others_rows(two_users, table):
    (a_id, a_tok), (b_id, b_tok) = two_users
    created = httpx.post(_rest(table), json={"user_id": a_id, **USER_TABLES[table]}, headers=_headers(a_tok), timeout=20)
    assert created.status_code == 201, f"A could not insert its own {table} row: {created.text[:200]}"
    row_id = created.json()[0]["id"]
    by_id = {"id": f"eq.{row_id}"}
    try:
        # Positive control: A sees its own row (so "empty" below means denied, not broken)
        assert len(httpx.get(_rest(table), params=by_id, headers=_headers(a_tok), timeout=20).json()) == 1

        # B can't read it — by id or by filtering on A's user_id
        assert httpx.get(_rest(table), params=by_id, headers=_headers(b_tok), timeout=20).json() == []
        assert httpx.get(_rest(table), params={"user_id": f"eq.{a_id}"}, headers=_headers(b_tok), timeout=20).json() == []

        # B can't change or delete it (RLS filters the row out → 0 rows affected)
        patched = httpx.patch(_rest(table), params=by_id, json=TAMPER[table], headers=_headers(b_tok), timeout=20)
        assert patched.status_code == 200 and patched.json() == []
        deleted = httpx.delete(_rest(table), params=by_id, headers=_headers(b_tok), timeout=20)
        assert deleted.status_code == 200 and deleted.json() == []
        still = httpx.get(_rest(table), params=by_id, headers=_headers(a_tok), timeout=20).json()
        assert len(still) == 1 and "pwned" not in str(still)

        # B can't create rows owned by A…
        forged = httpx.post(_rest(table), json={"user_id": a_id, **USER_TABLES[table]}, headers=_headers(b_tok), timeout=20)
        assert forged.status_code == 403, f"B inserted a row as A: {forged.status_code} {forged.text[:200]}"

        # …or hand one of its own rows over to A (UPDATE ... WITH CHECK)
        own = httpx.post(_rest(table), json={"user_id": b_id, **USER_TABLES[table]}, headers=_headers(b_tok), timeout=20)
        assert own.status_code == 201
        own_id = {"id": f"eq.{own.json()[0]['id']}"}
        handed = httpx.patch(_rest(table), params=own_id, json={"user_id": a_id}, headers=_headers(b_tok), timeout=20)
        httpx.delete(_rest(table), params=own_id, headers=_headers(b_tok), timeout=20)
        assert handed.status_code == 403, f"B reassigned a row to A: {handed.status_code} {handed.text[:200]}"
    finally:
        httpx.delete(_rest(table), params=by_id, headers=_headers(a_tok), timeout=20)


def test_signed_in_user_cannot_read_fingerprints(two_users):
    (_, a_tok), _ = two_users
    res = httpx.get(_rest("fingerprints"), params={"select": "repo_url", "limit": "5"}, headers=_headers(a_tok), timeout=20)
    assert _denied_or_empty(res), f"authenticated user read fingerprints: {res.status_code} {res.text[:200]}"
