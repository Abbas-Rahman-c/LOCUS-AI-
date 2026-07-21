"""
Retrieval router — API endpoints for natural language QA over retrieved decisions.
"""
from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.dependencies import TenantContext, get_current_tenant
from database.pool import get_db_pool
from modules.retrieval import service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/retrieval", tags=["retrieval"])


class AskRequest(BaseModel):
    query: str = Field(..., description="The natural language question to ask")
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
    ctx: TenantContext = Depends(get_current_tenant),
) -> StreamingResponse:
    """
    Takes a question, retrieves relevant decisions scoped to the tenant,
    and returns a streamed, cited answer.

    Authentication is enforced via the mandatory tenant-scoped JWT; the
    tenant_id is taken exclusively from the authenticated TenantContext.
    """
    pool = get_db_pool()

    try:
        # 1. Retrieve grounded decisions matching the query and filters
        decisions = await service.retrieve_decisions(
            query=body.query,
            tenant_id=ctx.tenant_id,
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
