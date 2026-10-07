"""Per-user rate limits on review / chat / analyze (backend/src/core/rate_limit.py)."""
from __future__ import annotations

import fakeredis
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.src.core import analysis_store, rate_limit
from backend.src.core.models import InsightsAgentOutput
from backend.src.core.redis_client import reset_redis, set_redis
from backend.src.routes import analyze_routes, chat_routes

USER = "3f2b8c1e-9a4d-4e57-8b1a-2c6d9e0f1a2b"
OTHER = "9d1c7a2e-5b3f-4c18-a6e9-0f2b8c4d7e11"
REPO = "https://github.com/acme/demo"


@pytest.fixture()
def fake_redis():
    client = fakeredis.FakeStrictRedis(server=fakeredis.FakeServer())
    set_redis(client)
    yield client
    reset_redis()


@pytest.fixture()
def limits(monkeypatch, fake_redis):
    """Limits on (conftest turns them off), small numbers, no global cap unless a test sets one."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_REVIEWS_PER_HOUR", "3")
    monkeypatch.setenv("RATE_LIMIT_CHATS_PER_HOUR", "2")
    monkeypatch.setenv("RATE_LIMIT_ANALYZES_PER_HOUR", "1")
    for name in ("RATE_LIMIT_REVIEWS_PER_DAY", "RATE_LIMIT_CHATS_PER_DAY", "RATE_LIMIT_ANALYZES_PER_DAY"):
        monkeypatch.setenv(name, "0")
    monkeypatch.delenv("RATE_LIMIT_EXEMPT_USERS", raising=False)


@pytest.fixture()
def clock(monkeypatch):
    now = {"t": 1_000_000.0}
    monkeypatch.setattr(rate_limit.time, "time", lambda: now["t"])
    return now


@pytest.fixture()
def client(limits, login):
    from backend.src.main import app

    login(USER)
    with TestClient(app) as c:
        yield c


def _reject(user_id: str, action=rate_limit.REVIEW) -> HTTPException:
    with pytest.raises(HTTPException) as exc:
        rate_limit.enforce(user_id, action)
    return exc.value


# ── limiter ──────────────────────────────────────────────────────────────────


def test_allows_the_limit_then_429_with_retry_after(limits, clock):
    for _ in range(3):
        rate_limit.enforce(USER, rate_limit.REVIEW)
    err = _reject(USER)
    assert err.status_code == 429
    assert err.headers["Retry-After"] == "3600"
    assert err.detail == "You've reached the demo limit of 3 reviews per hour. Try again in 1 hour."


def test_users_and_actions_are_counted_separately(limits, clock):
    for _ in range(3):
        rate_limit.enforce(USER, rate_limit.REVIEW)
    rate_limit.enforce(OTHER, rate_limit.REVIEW)
    rate_limit.enforce(USER, rate_limit.CHAT)


def test_window_slides(limits, clock):
    rate_limit.enforce(USER, rate_limit.REVIEW)       # t=0
    clock["t"] += 1800
    rate_limit.enforce(USER, rate_limit.REVIEW)       # t=30m
    rate_limit.enforce(USER, rate_limit.REVIEW)
    err = _reject(USER)
    assert err.headers["Retry-After"] == "1800"       # until the t=0 request ages out
    assert "30 minutes" in err.detail
    clock["t"] += 1801
    rate_limit.enforce(USER, rate_limit.REVIEW)       # first one aged out
    _reject(USER)


def test_rejected_requests_do_not_extend_the_wait(limits, clock):
    for _ in range(3):
        rate_limit.enforce(USER, rate_limit.REVIEW)
    for _ in range(5):
        clock["t"] += 600
        _reject(USER)
    clock["t"] += 601                                  # 3601 s after the first three
    rate_limit.enforce(USER, rate_limit.REVIEW)


def test_exempt_users_and_disabled_switch(limits, clock, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_EXEMPT_USERS", f" {OTHER} , someone-else")
    for _ in range(10):
        rate_limit.enforce(OTHER, rate_limit.REVIEW)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    for _ in range(10):
        rate_limit.enforce(USER, rate_limit.REVIEW)


def test_global_daily_cap_and_it_does_not_eat_user_quota(limits, clock, monkeypatch, fake_redis):
    monkeypatch.setenv("RATE_LIMIT_REVIEWS_PER_DAY", "2")
    rate_limit.enforce(USER, rate_limit.REVIEW)
    rate_limit.enforce(OTHER, rate_limit.REVIEW)
    err = _reject(USER)
    assert err.status_code == 429
    assert "The public demo has used up today's reviews" in err.detail
    # The rejected call isn't left in USER's hourly window.
    assert fake_redis.zcard(f"ratelimit:review:user:{USER}") == 1


def test_redis_down_allows_the_request(limits, monkeypatch):
    class Down:
        def pipeline(self, *a, **k):
            raise ConnectionError("redis down")

    monkeypatch.setattr(rate_limit, "get_redis", lambda: Down())
    rate_limit.enforce(USER, rate_limit.REVIEW)


def test_bad_env_value_falls_back_to_default(limits, clock, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REVIEWS_PER_HOUR", "lots")
    for _ in range(rate_limit.REVIEW.hourly_default):
        rate_limit.enforce(USER, rate_limit.REVIEW)
    _reject(USER)


# ── routes ───────────────────────────────────────────────────────────────────


def _mock_review(c: TestClient, repo_url: str = REPO):
    return c.post("/api/reviews", json={"repo_url": repo_url, "code": "x = 1\n", "mock": True})


def test_review_route_returns_friendly_429(client):
    for _ in range(3):
        assert _mock_review(client).status_code == 202
    res = _mock_review(client)
    assert res.status_code == 429
    assert res.headers["retry-after"] == "3600"
    assert res.json()["detail"].startswith("You've reached the demo limit of 3 reviews per hour.")


def test_invalid_review_request_does_not_use_quota(client):
    for _ in range(5):
        assert _mock_review(client, "not-a-repo").status_code == 400
    for _ in range(3):
        assert _mock_review(client).status_code == 202


def test_chat_route_is_limited(client, monkeypatch):
    monkeypatch.setattr(
        chat_routes, "get_insights",
        lambda **k: InsightsAgentOutput(answer="a", repos_used=[REPO], code_chunks_retrieved=0),
    )
    body = {"message": "how do I name things?", "selected_repo_urls": [REPO]}
    assert client.post("/api/chat", json=body).status_code == 200
    assert client.post("/api/chat", json=body).status_code == 200
    res = client.post("/api/chat", json=body)
    assert res.status_code == 429
    assert "2 questions per hour" in res.json()["detail"]
    # Empty messages are rejected before counting.
    assert client.post("/api/chat", json={**body, "message": "  "}).status_code == 400


def test_analyze_job_reattach_is_free_new_job_is_limited(client, monkeypatch):
    monkeypatch.setattr(analyze_routes, "enqueue_analyze_job", lambda *a, **k: None)
    first = client.post("/api/analyze-jobs", json={"repo_url": REPO})
    assert first.status_code == 202
    # Still queued → the same job comes back, no quota used.
    again = client.post("/api/analyze-jobs", json={"repo_url": REPO})
    assert again.status_code == 200
    assert again.json()["job_id"] == first.json()["job_id"]
    # A different repo is a new job → over the 1/hour limit.
    res = client.post("/api/analyze-jobs", json={"repo_url": "https://github.com/acme/other"})
    assert res.status_code == 429
    assert "1 repo analysis per hour" in res.json()["detail"]
    assert analysis_store.get_record(USER, "https://github.com/acme/other") is None


def test_sync_analyze_route_is_limited(client, monkeypatch):
    monkeypatch.setattr(analyze_routes, "run_analysis", lambda *a, **k: {"ok": True})
    assert client.post("/api/analyze-repo", json={"repo_url": REPO}).status_code == 200
    assert client.post("/api/analyze-repo", json={"repo_url": REPO}).status_code == 429


def test_cors_allows_configured_origin(monkeypatch):
    from backend.src import main

    monkeypatch.setenv("ALLOWED_ORIGINS", "https://personacr.example.com/, http://localhost:5173")
    origins = main.allowed_origins()
    assert "https://personacr.example.com" in origins
    assert origins.count("http://localhost:5173") == 1
