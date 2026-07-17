"""
Retrieval router — API endpoints for natural language QA over retrieved decisions.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.dependencies import TenantContext
from database.pool import get_db_pool
from modules.retrieval import service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/retrieval", tags=["retrieval"])

_bearer_optional = HTTPBearer(auto_error=False)


async def get_current_tenant_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
) -> Optional[TenantContext]:
    """
    Optional FastAPI dependency: Try to validate the Authorization header if present.
    Returns None if missing or invalid, letting the controller fallback to request body.
    """
    if not credentials:
        return None
    try:
        from modules.auth.service import verify_tenant_jwt
        payload = verify_tenant_jwt(credentials.credentials)
        return TenantContext(
            user_id=payload["sub"],
            tenant_id=payload["tenant_id"],
            role=payload.get("role", "member"),
        )
    except Exception as exc:
        log.debug("Optional JWT validation failed: %s", exc)
        return None


class AskRequest(BaseModel):
    query: str = Field(..., description="The natural language question to ask")
    tenant_id: Optional[str] = Field(
        None,
        description="TEMPORARY: fallback tenant UUID for testing/interim auth when JWT is not set"
    )
    filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional filters: status, confidence_min, actor, date_range"
    )
    limit: int = Field(10, ge=1, le=50, description="Max decisions to retrieve")
    offset: int = Field(0, ge=0, description="Pagination offset")


@router.post(
    "/ask",
    summary="Ask a question grounded in decisions (streams answer)",
)
async def ask_question(
    body: AskRequest,
    ctx: Optional[TenantContext] = Depends(get_current_tenant_optional),
) -> StreamingResponse:
    """
    Takes a question, retrieves relevant decisions scoped to the tenant,
    and returns a streamed, cited answer.
    
    Supports authenticating via standard tenant JWT or an interim request body fallback.
    """
    tenant_id = None
    if ctx:
        tenant_id = ctx.tenant_id
    elif body.tenant_id:
        tenant_id = body.tenant_id
        log.warning(
            "TEMPORARY AUTH BYPASS IN USE: Using request-body tenant_id fallback: %s",
            tenant_id
        )

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid tenant JWT or request-body tenant_id.",
        )

    try:
        uuid.UUID(str(tenant_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant_id format. Must be a valid UUID.",
        )

    pool = get_db_pool()

    try:
        # 1. Retrieve grounded decisions matching the query and filters
        decisions = await service.retrieve_decisions(
            query=body.query,
            tenant_id=tenant_id,
            filters=body.filters,
            limit=body.limit,
            offset=body.offset,
            pool=pool,
        )

        # 2. Return StreamingResponse chunking LLM synthesis output
        return StreamingResponse(
            service.synthesize_answer(query=body.query, retrieved_decisions=decisions),
            media_type="application/x-ndjson",
        )

    except Exception as exc:
        log.exception("Retrieval QA pipeline failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the request.",
        ) from exc
