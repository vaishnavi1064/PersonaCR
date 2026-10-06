"""Guest cleanup: POST (keepalive on tab close) or DELETE, and only for the caller's own guest session."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.src.routes import analyze_routes as ar


@pytest.fixture
def client(login):
    from backend.src.main import app

    login("guest_abc123")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def deleted(monkeypatch):
    calls: list[str] = []

    def fake_delete(session_id: str) -> int:
        calls.append(session_id)
        return 2

    monkeypatch.setattr(ar, "delete_guest_collections", fake_delete)
    return calls


@pytest.mark.parametrize("method", ["post", "delete"])
def test_guest_cleanup_accepts_beacon_post_and_delete(client, deleted, method):
    res = getattr(client, method)("/api/cleanup-guest/guest_abc123")
    assert res.status_code == 200  # was 405 for POST — tab-close cleanup never ran
    assert res.json()["deleted"] == 2
    assert deleted == ["guest_abc123"]


def test_another_guests_session_is_403(client, deleted):
    res = client.post("/api/cleanup-guest/guest_someone_else")
    assert res.status_code == 403
    assert deleted == []


def test_beacon_post_ignores_non_guest_ids(client, deleted):
    res = client.post("/api/cleanup-guest/3f2b8c1e-9a4d-4e57-8b1a-2c6d9e0f1a2b")
    assert res.status_code == 200
    assert res.json()["deleted"] == 0
    assert deleted == []  # never touches a real user's collections


def test_beacon_route_not_in_schema(client):
    ops = [op.get("operationId") for path in client.get("/openapi.json").json()["paths"].values() for op in path.values()]
    assert "cleanup_guest" in ops
    assert "cleanup_guest_beacon" not in ops  # one MCP tool, not two
