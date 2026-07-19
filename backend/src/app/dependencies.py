"""
Shared FastAPI dependencies: DB session, auth user extraction, tenant context.

Usage in any router:
    @router.get("/decisions")
    async def list_decisions(ctx: TenantContext = Depends(get_current_tenant)):
        ...

Every protected endpoint MUST inject this dependency — no exceptions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError

from modules.auth.service import verify_tenant_jwt

log = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class TenantContext:
    """Caller identity resolved from the tenant-scoped JWT."""
    user_id: str
    tenant_id: str
    role: str


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> TenantContext:
    """
    FastAPI dependency: validate the Authorization: Bearer <token> header and
    return a TenantContext with the caller's user_id, tenant_id, and role.

    Raises HTTP 401 on any validation failure (missing, expired, bad signature,
    missing tenant_id claim).  This dependency must be injected into every
    protected route handler.
    """
    token = credentials.credentials

    try:
        payload = verify_tenant_jwt(token)
    except ExpiredSignatureError:
        log.debug("Tenant JWT expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (JWTError, ValueError) as exc:
        log.debug("Tenant JWT invalid: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TenantContext(
        user_id=payload["sub"],
        tenant_id=payload["tenant_id"],
        role=payload.get("role", "member"),
    )
