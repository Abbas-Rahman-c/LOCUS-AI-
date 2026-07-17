"""
Auth router — POST /auth/session

This is the only endpoint that accepts a raw Supabase access_token.
It returns a tenant-scoped JWT that the client uses for all subsequent calls.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from database.pool import get_db_pool
from modules.auth.schemas import SessionRequest, SessionResponse
from modules.auth.service import AuthError, exchange_supabase_token

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/session",
    response_model=SessionResponse,
    summary="Exchange a Supabase access_token for a tenant-scoped JWT",
)
async def create_session(body: SessionRequest) -> SessionResponse:
    """
    Called by the browser immediately after Supabase OAuth completes.

    The client presents its Supabase access_token; the backend verifies it,
    resolves the tenant, and returns a signed tenant-scoped JWT.

    The client stores ONLY this token going forward — no Supabase secrets or
    raw DB credentials ever reach the browser.
    """
    pool = get_db_pool()
    try:
        return await exchange_supabase_token(body.supabase_token, pool)
    except AuthError as exc:
        log.warning("Auth failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:
        log.exception("Unexpected error during session creation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session creation failed",
        ) from exc
