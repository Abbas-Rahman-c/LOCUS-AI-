"""
Supabase JWT verifier.

Fetches JWKS from the Supabase project's well-known endpoint and validates
the incoming access_token using python-jose.  The JWKS response is cached for
the lifetime of the process (keys rotate rarely; an LRU is overkill for MVP).
"""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode

from common.config import get_supabase_settings

log = logging.getLogger(__name__)


class SupabaseVerificationError(Exception):
    """Raised when a Supabase JWT cannot be verified."""


@lru_cache(maxsize=1)
def _fetch_jwks_cached(jwks_url: str) -> list[dict]:
    """Synchronously fetch the JWKS and cache the list of keys.

    We use httpx in sync mode here because this is called once at startup
    (or on first request) and caching removes repeated network calls.
    """
    try:
        response = httpx.get(jwks_url, timeout=10)
        response.raise_for_status()
        return response.json()["keys"]
    except Exception as exc:
        raise SupabaseVerificationError(
            f"Failed to fetch JWKS from {jwks_url}: {exc}"
        ) from exc


def _get_signing_key(token: str) -> str:
    """Return the RSA public key matching the JWT's kid header."""
    settings = get_supabase_settings()
    jwks_url = settings.get_jwks_url()

    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise SupabaseVerificationError(f"Cannot parse JWT header: {exc}") from exc

    kid = header.get("kid")
    keys = _fetch_jwks_cached(jwks_url)

    for key_data in keys:
        if kid and key_data.get("kid") != kid:
            continue
        try:
            return jwk.construct(key_data).public_key().export_key().decode("utf-8")
        except Exception:
            continue

    raise SupabaseVerificationError(
        f"No matching key found in JWKS for kid={kid!r}"
    )


def verify_supabase_token(token: str) -> dict:
    """Verify a Supabase access_token and return its decoded claims.

    Raises SupabaseVerificationError on any failure (expired, bad sig, etc.).
    """
    signing_key = _get_signing_key(token)
    settings = get_supabase_settings()

    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience="authenticated",
            options={"verify_aud": True},
        )
    except JWTError as exc:
        raise SupabaseVerificationError(f"JWT verification failed: {exc}") from exc

    if not payload.get("sub"):
        raise SupabaseVerificationError("JWT missing 'sub' claim")

    return payload
