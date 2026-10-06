"""GET /api/repos — user's imported repos joined with cached fingerprints."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.src.routes import repo_routes

USER = "3f2b8c1e-9a4d-4e57-8b1a-2c6d9e0f1a2b"


class FakeDB:
    def __init__(self, user_repos: list[dict], fingerprints: list[dict], fail: str | None = None):
        self.user_repos = user_repos
        self.fingerprints = fingerprints
        self.fail = fail
        self.fp_params: dict | None = None

    def select_many(self, table, filters=None, select="*", order=None, limit=None, offset=0):
        assert table == "user_repos"
        if self.fail == "user_repos":
            raise httpx.HTTPError("boom")
        assert filters == {"user_id": USER}
        assert order == "analyzed_at.desc"
        return list(self.user_repos)

    def select_raw(self, table, params):
        assert table == "fingerprints"
        if self.fail == "fingerprints":
            raise httpx.HTTPError("boom")
        self.fp_params = params
        return list(self.fingerprints)


@pytest.fixture(autouse=True)
def fake_redis():
    """GET /api/repos merges analysis status from Redis — keep tests off the network."""
    import fakeredis

    from backend.src.core.redis_client import reset_redis, set_redis

    client = fakeredis.FakeStrictRedis(server=fakeredis.FakeServer())
    set_redis(client)
    yield client
    reset_redis()


@pytest.fixture
def client():
    from backend.src.main import app

    with TestClient(app) as c:
        yield c


def _use(monkeypatch, db: FakeDB) -> FakeDB:
    monkeypatch.setattr(repo_routes, "SupabaseREST", lambda: db)
    return db


def test_joins_fingerprint_and_dedupes_newest_first(client, monkeypatch):
    db = _use(monkeypatch, FakeDB(
        user_repos=[
            {"repo_url": "https://github.com/acme/api/", "functions_count": 40, "languages": ["python"], "analyzed_at": "2026-10-02T00:00:00Z"},
            {"repo_url": "https://github.com/acme/web", "functions_count": 12, "languages": ["typescript"], "analyzed_at": "2026-10-01T00:00:00Z"},
            {"repo_url": "https://github.com/acme/api", "functions_count": 35, "languages": ["python"], "analyzed_at": "2026-09-01T00:00:00Z"},
        ],
        fingerprints=[
            {"repo_url": "https://github.com/acme/api", "fingerprint_data": {"type_hint_usage": 0.79, "naming_convention": "snake_case"},
             "num_functions": 42, "languages": ["python"], "last_commit_sha": "abc", "updated_at": "2026-10-02T01:00:00Z"},
        ],
    ))

    res = client.get("/api/repos", params={"user_id": USER})
    assert res.status_code == 200
    repos = res.json()["repos"]

    assert [r["repo_url"] for r in repos] == ["https://github.com/acme/api", "https://github.com/acme/web"]
    api, web = repos
    assert api["repo_name"] == "acme/api"
    assert api["fingerprint"] == {"type_hint_usage": 0.79, "naming_convention": "snake_case"}
    assert api["functions_count"] == 42  # fingerprint count wins over the user_repos row
    assert api["analyzed_at"] == "2026-10-02T01:00:00Z"
    assert web["fingerprint"] is None  # no cached fingerprint → UI shows "Added", not fake stats
    assert web["functions_count"] == 12
    # one batched fingerprint lookup with quoted URLs (":" and "/" are PostgREST-reserved)
    assert db.fp_params["repo_url"] == 'in.("https://github.com/acme/api","https://github.com/acme/web")'


@pytest.mark.parametrize("user_id", ["guest_1234", "anonymous", "not-a-uuid"])
def test_non_account_ids_get_empty_list_without_db(client, monkeypatch, user_id):
    def no_db():
        raise AssertionError("must not touch the database")

    monkeypatch.setattr(repo_routes, "SupabaseREST", no_db)
    res = client.get("/api/repos", params={"user_id": user_id})
    assert res.status_code == 200
    assert res.json() == {"repos": []}


def test_no_repos_skips_fingerprint_lookup(client, monkeypatch):
    db = _use(monkeypatch, FakeDB(user_repos=[], fingerprints=[]))
    res = client.get("/api/repos", params={"user_id": USER})
    assert res.json() == {"repos": []}
    assert db.fp_params is None


@pytest.mark.parametrize("fail", ["user_repos", "fingerprints"])
def test_database_failure_is_502_not_empty(client, monkeypatch, fail):
    _use(monkeypatch, FakeDB(
        user_repos=[{"repo_url": "https://github.com/acme/api", "analyzed_at": "2026-10-02T00:00:00Z"}],
        fingerprints=[],
        fail=fail,
    ))
    res = client.get("/api/repos", params={"user_id": USER})
    assert res.status_code == 502


def test_user_id_is_required(client):
    assert client.get("/api/repos").status_code == 422


# ── POST /api/analyze-repo reports when the analysis it returns was made ─────

def test_analyze_cached_returns_stored_timestamp(monkeypatch):
    from unittest.mock import MagicMock

    from backend.src.routes import analyze_routes as ar

    from backend.src.core import analysis as analysis_mod

    monkeypatch.setattr(analysis_mod, "SupabaseREST", MagicMock())
    monkeypatch.setattr(analysis_mod, "get_cached_fingerprint", lambda *a, **k: {
        "_cache_status": "fresh", "repo_name": "api", "fingerprint_data": {"type_hint_usage": 0.5},
        "num_functions": 7, "last_commit_sha": "abc", "updated_at": "2026-09-30T12:00:00+00:00",
    })
    out = ar.analyze_repo(ar.AnalyzeRequest(repo_url="https://github.com/acme/api", user_id=USER))
    assert out["cache_status"] == "fresh"
    # a cache hit must not look like it was analyzed just now
    assert out["analyzed_at"] == "2026-09-30T12:00:00+00:00"


def test_analyze_fresh_returns_now(monkeypatch, tmp_path):
    from datetime import datetime, timedelta, timezone
    from unittest.mock import MagicMock

    from backend.src.routes import analyze_routes as ar

    from backend.src.core import analysis as analysis_mod
    from tests.conftest import make_chunk

    monkeypatch.setattr(analysis_mod, "SupabaseREST", MagicMock())
    monkeypatch.setattr(analysis_mod, "ingest_repo", lambda url, token=None, **_: ([make_chunk("f", "def f(x: int) -> int:\n    return x")], "sha1"))
    monkeypatch.setattr(analysis_mod, "embed_and_store", lambda *a, **k: {"collection": "c", "chunks_embedded": 1})
    monkeypatch.setattr(analysis_mod, "save_fingerprint", MagicMock())
    out = ar.analyze_repo(ar.AnalyzeRequest(repo_url="https://github.com/acme/api", user_id=USER, force_refresh=True))
    assert out["cache_status"] == "new"
    analyzed = datetime.fromisoformat(out["analyzed_at"])
    assert abs(datetime.now(timezone.utc) - analyzed) < timedelta(seconds=30)
