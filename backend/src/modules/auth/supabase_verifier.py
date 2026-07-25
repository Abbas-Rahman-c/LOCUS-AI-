"""
Supabase JWT verifier.

Fetches JWKS from the Supabase project's well-known endpoint and validates
the incoming access_token using python-jose. The JWKS response is cached for
the lifetime of the process (keys rotate rarely; an LRU is overkill for MVP).
"""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from jose import JWTError, jwt

from common.config import get_supabase_settings

log = logging.getLogger(__name__)


class SupabaseVerificationError(Exception):
    """Raised when a Supabase JWT cannot be verified."""


@lru_cache(maxsize=1)
def _fetch_jwks_cached(jwks_url: str) -> list[dict]:
    """Synchronously fetch the JWKS and cache the list of keys."""
    try:
        response = httpx.get(jwks_url, timeout=10)
        response.raise_for_status()
        return response.json()["keys"]
    except Exception as exc:
        raise SupabaseVerificationError(
            f"Failed to fetch JWKS from {jwks_url}: {exc}"
        ) from exc


def _get_signing_key_data(token: str) -> dict:
    """Return the raw JWK dict matching the JWT's kid header."""
    settings = get_supabase_settings()
    jwks_url = settings.get_jwks_url()

    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise SupabaseVerificationError(f"Cannot parse JWT header: {exc}") from exc

    kid = header.get("kid")
    keys = _fetch_jwks_cached(jwks_url)

    for key_data in keys:
        if kid and key_data.get("kid") == kid:
            return key_data

    _fetch_jwks_cached.cache_clear()
    keys = _fetch_jwks_cached(jwks_url)
    for key_data in keys:
        if kid and key_data.get("kid") == kid:
            return key_data

    raise SupabaseVerificationError(
        f"No matching key found in JWKS for kid={kid!r}"
    )


def verify_supabase_token(token: str) -> dict:
    """Verify a Supabase access_token and return its decoded claims."""
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise SupabaseVerificationError(f"Cannot parse JWT header: {exc}") from exc

    alg = header.get("alg")
    if alg not in ("RS256", "ES256", "HS256"):
        raise SupabaseVerificationError(f"Unsupported JWT algorithm: {alg!r}")

    signing_key_data = _get_signing_key_data(token)

    try:
        payload = jwt.decode(
            token,
            signing_key_data,
            algorithms=[alg],
            audience="authenticated",
            options={"verify_aud": True},
        )
    except JWTError as exc:
        raise SupabaseVerificationError(f"JWT verification failed: {exc}") from exc

    if not payload.get("sub"):
        raise SupabaseVerificationError("JWT missing 'sub' claim")

    return payload
