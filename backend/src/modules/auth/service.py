"""
Auth service: exchanges a verified Supabase token for a tenant-scoped JWT.

Token format (HS256, signed with APP_SECRET_KEY):
  {
    "iss": "locus-ai",
    "sub": "<auth_user_id>",
    "tenant_id": "<tenant_uuid>",
    "role": "owner|admin|member",
    "iat": <unix>,
    "exp": <unix>   (iat + 86400 by default)
  }

The client (browser or MCP client) stores ONLY this token - no raw Supabase
secret or DB credentials ever leave the backend.
"""
from __future__ import annotations

import logging
import os
import time
import uuid

import asyncpg
from jose import jwt

from modules.auth.schemas import SessionResponse
from modules.auth.supabase_verifier import SupabaseVerificationError, verify_supabase_token

log = logging.getLogger(__name__)

ALGORITHM = "HS256"
ISSUER = "locus-ai"
TTL_SECONDS = 86_400  # 24 h


class AuthError(Exception):
    """Raised when auth cannot be completed (bad token, no membership, etc.)."""


def _secret_key() -> str:
    key = os.environ.get("APP_SECRET_KEY", "")
    if not key:
        raise RuntimeError(
            "APP_SECRET_KEY is not set - cannot sign session tokens."
        )
    return key


def issue_tenant_jwt(
    user_id: str,
    tenant_id: str,
    role: str,
    ttl: int = TTL_SECONDS,
) -> str:
    """Sign and return a tenant-scoped JWT."""
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def verify_tenant_jwt(token: str) -> dict:
    """Verify and decode a tenant-scoped JWT.

    Raises jose.JWTError (which callers should map to HTTP 401).
    """
    payload = jwt.decode(
        token,
        _secret_key(),
        algorithms=[ALGORITHM],
        issuer=ISSUER,
    )
    if not payload.get("tenant_id"):
        raise ValueError("JWT missing tenant_id claim")
    return payload


async def exchange_supabase_token(
    supabase_token: str,
    pool: asyncpg.Pool,
) -> SessionResponse:
    """
    Verify supabase_token, look up the caller's membership, and return a
    tenant-scoped SessionResponse.

    Steps:
      1. Verify Supabase JWT (signature, expiry, audience).
      2. Extract auth_user_id (sub).
      3. Look up memberships for that user_id.
      4. Issue and return a tenant-scoped JWT.
    """
    # 1. Verify
    try:
        claims = verify_supabase_token(supabase_token)
    except SupabaseVerificationError as exc:
        raise AuthError(f"Invalid Supabase token: {exc}") from exc

    auth_user_id: str = claims["sub"]

    # 2. Look up membership - MUST use the admin pool, not the tenant-scoped
    # one passed in. RLS requires app.current_tenant_id to already be set,
    # but this lookup's entire job is determining what that tenant_id
    # should be - a genuine chicken-and-egg case, not a security shortcut.
    from database.pool import get_admin_db_pool

    async with get_admin_db_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT m.tenant_id, m.role
            FROM memberships m
            WHERE m.user_id = $1
            ORDER BY m.created_at ASC
            LIMIT 1
            """,
            uuid.UUID(auth_user_id),
        )

    if row is None:
        raise AuthError(
            f"No tenant membership found for user {auth_user_id}. "
            "The account may not have been provisioned correctly."
        )

    tenant_id = str(row["tenant_id"])
    role = row["role"]

    # 3. Issue tenant JWT
    token = issue_tenant_jwt(auth_user_id, tenant_id, role)

    log.info(
        "Issued tenant JWT: user=%s tenant=%s role=%s",
        auth_user_id,
        tenant_id,
        role,
    )
    return SessionResponse(token=token, tenant_id=tenant_id, role=role)
