"""
Auth request/response schemas.
"""
from __future__ import annotations

from pydantic import BaseModel


class SessionRequest(BaseModel):
    """Body sent by the browser: the raw Supabase access_token."""
    supabase_token: str


class SessionResponse(BaseModel):
    """Tenant-scoped JWT returned to the client."""
    token: str
    tenant_id: str
    role: str
    expires_in: int = 86_400  # seconds
