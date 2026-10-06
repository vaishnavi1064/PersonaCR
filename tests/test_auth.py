"""
Backend auth: every /api/* route needs a valid Supabase access token, and the
caller's id comes from the token's `sub` — never the body or query string.

Tokens here are real ES256 JWTs signed with a throwaway key; the JWKS client is
swapped for one that serves the matching public key, so signature, expiry,
audience and issuer checks all run for real.
"""
from __future__ import annotations

import re
import time
import uuid
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.src.core import auth

SUPABASE_URL = "https://testproj.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
KID = "test-key"
SUB = "3f2b8c1e-9a4d-4e57-8b1a-2c6d9e0f1a2b"
ATTACKER = "11111111-2222-4333-8444-555555555555"

_PRIVATE = ec.generate_private_key(ec.SECP256R1())
_OTHER_PRIVATE = ec.generate_private_key(ec.SECP256R1())


class _FakeJWKS:
    def __init__(self) -> None:
        jwk = jwt.algorithms.ECAlgorithm.to_jwk(_PRIVATE.public_key(), as_dict=True)
        self.key = jwt.PyJWK({**jwk, "alg": "ES256", "kid": KID, "use": "sig"})

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK:
        if jwt.get_unverified_header(token).get("kid") != KID:
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")
        return self.key


@pytest.fixture(autouse=True)
def _supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_URL)
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setattr(auth, "_jwks_client", lambda url: _FakeJWKS())


def make_token(sub: str | None = SUB, *, key: Any = _PRIVATE, alg: str = "ES256", kid: str = KID, **claims: Any) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub, "aud": "authenticated", "iss": ISSUER, "role": "authenticated",
        "iat": now, "exp": now + 3600, "is_anonymous": False,
    }
    payload.update(claims)
    if sub is None:
        del payload["sub"]
    return jwt.encode(payload, key, algorithm=alg, headers={"kid": kid})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    from backend.src.main import app

    with TestClient(app) as c:
        yield c


# ── 401 on missing / invalid tokens ─────────────────────────────────────────

def _api_routes() -> list[tuple[str, str]]:
    from backend.src.main import app

    out = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api"):
            path = re.sub(r"\{[^}]+\}", "guest_x", route.path)
            out += [(method, path) for method in sorted(route.methods)]
    return out


def test_every_api_route_is_covered():
    paths = {p for _, p in _api_routes()}
    assert {"/api/analyze-repo", "/api/analyze-jobs", "/api/repos", "/api/chat", "/api/review", "/api/reviews"} <= paths


@pytest.mark.parametrize("method,path", _api_routes())
def test_every_api_route_rejects_missing_token(client, method, path):
    res = client.request(method, path, json={})
    assert res.status_code == 401, f"{method} {path} is reachable without a token"
    assert res.headers.get("www-authenticate") == "Bearer"


def test_health_and_metrics_stay_open(client):
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200


INVALID = {
    "garbage": "not-a-jwt",
    "wrong signing key": make_token(key=_OTHER_PRIVATE),
    "unknown kid": make_token(kid="rotated-away"),
    "expired": make_token(exp=int(time.time()) - 60),
    "wrong audience": make_token(aud="anon"),
    "wrong issuer": make_token(iss="https://evil.supabase.co/auth/v1"),
    "no subject": make_token(sub=None),
    "alg none": jwt.encode({"sub": SUB, "aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 60}, None, algorithm="none"),
    "HS256 without a configured secret": make_token(key="x" * 32, alg="HS256"),
}


@pytest.mark.parametrize("case", INVALID)
def test_invalid_tokens_are_401(client, case):
    res = client.get("/api/repos", headers=bearer(INVALID[case]))
    assert res.status_code == 401, case


def test_non_bearer_scheme_is_401(client):
    assert client.get("/api/repos", headers={"Authorization": f"Basic {make_token()}"}).status_code == 401


def test_hs256_accepted_only_with_the_legacy_secret(monkeypatch):
    secret = "legacy-jwt-secret-at-least-32-bytes!"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    assert auth.verify_token(make_token(key=secret, alg="HS256")).sub == SUB
    with pytest.raises(jwt.InvalidSignatureError):
        auth.verify_token(make_token(key="some-other-secret-of-32-bytes-long", alg="HS256"))


def test_hs256_signed_with_the_public_key_is_rejected(monkeypatch):
    """Algorithm confusion: the JWKS public key is never accepted as an HMAC secret."""
    import base64
    import hashlib
    import hmac
    import json

    from cryptography.hazmat.primitives import serialization

    monkeypatch.setenv("SUPABASE_JWT_SECRET", "legacy-jwt-secret-at-least-32-bytes!")
    pem = _PRIVATE.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

    def b64(raw: bytes) -> bytes:
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    signing_input = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": KID}).encode()) + b"." + b64(json.dumps(
        {"sub": SUB, "aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 60}
    ).encode())
    forged = (signing_input + b"." + b64(hmac.new(pem, signing_input, hashlib.sha256).digest())).decode()
    with pytest.raises(jwt.InvalidSignatureError):
        auth.verify_token(forged)


def test_jwks_unreachable_is_503_not_401(client, monkeypatch):
    class Down:
        def get_signing_key_from_jwt(self, token):
            raise jwt.PyJWKClientConnectionError("connection refused")

    monkeypatch.setattr(auth, "_jwks_client", lambda url: Down())
    assert client.get("/api/repos", headers=bearer(make_token())).status_code == 503


# ── the caller is the token's sub ───────────────────────────────────────────

def test_account_and_anonymous_tokens_map_to_user_ids():
    assert auth.verify_token(make_token()).user_id == SUB
    guest = auth.verify_token(make_token(is_anonymous=True))
    assert guest.is_anonymous and guest.user_id == f"guest_{SUB}"


def test_analyze_uses_token_sub_not_body_user_id(client, monkeypatch):
    from backend.src.routes import analyze_routes

    seen: list[str] = []
    monkeypatch.setattr(analyze_routes, "run_analysis", lambda url, *, user_id, **k: seen.append(user_id) or {"ok": True})
    body = {"repo_url": "https://github.com/acme/api", "user_id": ATTACKER}
    assert client.post("/api/analyze-repo", json=body, headers=bearer(make_token())).status_code == 200
    assert client.post("/api/analyze-repo", json=body, headers=bearer(make_token(is_anonymous=True))).status_code == 200
    assert seen == [SUB, f"guest_{SUB}"]


def test_chat_uses_token_sub_not_body_user_id(client, monkeypatch):
    from types import SimpleNamespace

    from backend.src.core.models import ChatMemoryInfo
    from backend.src.routes import chat_routes

    seen: list[str] = []

    def fake_insights(*, user_id, **kwargs):
        seen.append(user_id)
        return SimpleNamespace(answer="a", repos_used=[], code_chunks_retrieved=0, memory=ChatMemoryInfo(), error=None)

    monkeypatch.setattr(chat_routes, "get_insights", fake_insights)
    res = client.post(
        "/api/chat",
        json={"message": "hi", "selected_repo_urls": ["https://github.com/acme/api"], "user_id": ATTACKER},
        headers=bearer(make_token()),
    )
    assert res.status_code == 200 and seen == [SUB]


def test_repo_list_uses_token_sub_not_query_user_id(client, monkeypatch):
    from backend.src.routes import repo_routes

    filters_seen: list[dict] = []

    class DB:
        def select_many(self, table, filters=None, **kw):
            filters_seen.append(filters)
            return []

    monkeypatch.setattr(repo_routes, "SupabaseREST", DB)
    monkeypatch.setattr(repo_routes, "_analysis_records", lambda user_id: {})
    res = client.get("/api/repos", params={"user_id": ATTACKER}, headers=bearer(make_token()))
    assert res.status_code == 200 and filters_seen == [{"user_id": SUB}]


def test_jobs_are_only_visible_to_their_owner(client, monkeypatch):
    import fakeredis

    from backend.src.core import job_store
    from backend.src.core.redis_client import reset_redis, set_redis

    set_redis(fakeredis.FakeStrictRedis(server=fakeredis.FakeServer()))
    try:
        job_id = str(uuid.uuid4())
        job_store.create_job(job_id, meta={"kind": "review", "user_id": SUB})
        assert client.get(f"/api/reviews/{job_id}", headers=bearer(make_token())).status_code == 200
        assert client.get(f"/api/reviews/{job_id}", headers=bearer(make_token(sub=ATTACKER))).status_code == 404
        assert client.get(f"/api/analyze-jobs/{job_id}", headers=bearer(make_token(sub=ATTACKER))).status_code == 404
    finally:
        reset_redis()
