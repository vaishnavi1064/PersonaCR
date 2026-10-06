"""
Request authentication — every /api/* route requires a Supabase access token.

The token arrives as `Authorization: Bearer <jwt>`; the caller is the token's
`sub`. Request bodies and query strings never name the user.

Verification: asymmetric tokens (ES256/RS256) are checked against the project's
JWKS at {SUPABASE_URL}/auth/v1/.well-known/jwks.json — public keys, no secret.
HS256 tokens (the legacy shared secret) are accepted only when
SUPABASE_JWT_SECRET is set. Audience must be "authenticated" and the issuer
{SUPABASE_URL}/auth/v1.

Guests use Supabase anonymous sign-in: a real token with `is_anonymous: true`.
They map to `guest_<sub>`, so the existing guest paths keep working — nothing
saved to Postgres, Redis-only analysis records, Chroma cleanup on tab close.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv("backend/.env")

logger = logging.getLogger(__name__)

AUDIENCE = "authenticated"
_ASYMMETRIC_ALGS = {"ES256", "RS256", "EdDSA"}
_UNAUTHORIZED = {"WWW-Authenticate": "Bearer"}

_bearer = HTTPBearer(auto_error=False, description="Supabase access token")


@dataclass(frozen=True)
class AuthUser:
    sub: str            # Supabase auth.users id
    is_anonymous: bool  # anonymous sign-in (guest)

    @property
    def user_id(self) -> str:
        """The id the rest of the backend keys on: the account uuid, or guest_<sub>."""
        return f"guest_{self.sub}" if self.is_anonymous else self.sub


class AuthConfigError(RuntimeError):
    """The server can't verify tokens (misconfigured or JWKS unreachable) — not the caller's fault."""


def _supabase_url() -> str:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not url:
        raise AuthConfigError("SUPABASE_URL is not set")
    return url


@lru_cache(maxsize=1)
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    # Keys are cached for 10 minutes; an unknown kid (key rotation) forces a refetch.
    return jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=600)


def _signing_key(token: str, alg: str) -> tuple[Any, str]:
    """Key and the single algorithm allowed with it — never the JWKS key under HS256."""
    if alg in _ASYMMETRIC_ALGS:
        try:
            jwk = _jwks_client(f"{_supabase_url()}/auth/v1/.well-known/jwks.json").get_signing_key_from_jwt(token)
        except jwt.PyJWKClientConnectionError as e:
            raise AuthConfigError(f"JWKS unreachable: {e}") from e
        return jwk.key, jwk.algorithm_name
    if alg == "HS256":
        secret = os.getenv("SUPABASE_JWT_SECRET", "")
        if not secret:
            raise jwt.InvalidTokenError("HS256 token, but SUPABASE_JWT_SECRET is not set")
        return secret, "HS256"
    raise jwt.InvalidAlgorithmError(f"Unsupported token algorithm: {alg!r}")


def verify_token(token: str) -> AuthUser:
    """Verify signature, expiry, audience and issuer; raise jwt.PyJWTError if invalid."""
    alg = jwt.get_unverified_header(token).get("alg", "")
    key, allowed_alg = _signing_key(token, alg)
    claims = jwt.decode(
        token,
        key,
        algorithms=[allowed_alg],
        audience=AUDIENCE,
        issuer=f"{_supabase_url()}/auth/v1",
        options={"require": ["exp", "sub", "aud", "iss"]},
    )
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise jwt.InvalidTokenError("Token has no subject")
    return AuthUser(sub=sub, is_anonymous=bool(claims.get("is_anonymous", False)))


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> AuthUser:
    """FastAPI dependency: the verified caller, or 401."""
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Sign in required (missing bearer token).", headers=_UNAUTHORIZED)
    try:
        return verify_token(creds.credentials)
    except AuthConfigError as e:
        logger.error("Cannot verify access tokens: %s", e)
        raise HTTPException(status_code=503, detail="Sign-in can't be verified right now.")
    except jwt.PyJWTError as e:
        logger.info("Rejected access token: %s", e)
        raise HTTPException(status_code=401, detail="Invalid or expired session — sign in again.", headers=_UNAUTHORIZED)
