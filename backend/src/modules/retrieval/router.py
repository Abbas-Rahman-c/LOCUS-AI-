"""
Retrieval routes: POST /retrieval/query (retrieve + synthesize an answer),
GET /retrieval/status (DB pool health + last eval_report.json summary).

Registered in app/main.py under prefix /retrieval. Tenant is taken from the
request body for now rather than an auth dependency -- modules.app.
dependencies (auth user / tenant extraction) is not wired up anywhere in
this codebase yet (it's a stub, same as this router was before this
change), so this matches every other router's actual current state rather
than inventing auth machinery this change isn't scoped to build. Swapping
`request.tenant_id` for a `tenant_id: UUID = Depends(get_current_tenant_id)`
dependency once that exists is a one-line change to each handler's
signature.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID

import asyncpg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from database.pool import get_db_pool
from modules.retrieval.pipeline import RAGPipeline
from modules.retrieval.schemas import Citation

log = logging.getLogger(__name__)

router = APIRouter(prefix="/retrieval", tags=["retrieval"])

# backend/eval_report.json -- the default --out-dir in scripts/run_rag_eval.py.
_EVAL_REPORT_PATH = Path(__file__).resolve().parents[3] / "eval_report.json"


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1)
    tenant_id: UUID
    top_k: int = Field(default=10, ge=1, le=50)


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[Citation]
    grounded_in: list[UUID]


class StatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database: str
    last_eval_report: dict | None = None


@router.post("/query", response_model=QueryResponse)
async def query_decisions(request: QueryRequest) -> QueryResponse:
    pipeline = RAGPipeline()
    try:
        result = await pipeline.answer(request.question, request.tenant_id, top_k=request.top_k)
    except Exception as exc:  # noqa: BLE001 - surfaced as a 502, logged with full detail
        log.exception("retrieval query failed tenant_id=%s", request.tenant_id)
        raise HTTPException(status_code=502, detail=f"Retrieval failed: {exc}") from exc

    return QueryResponse(
        answer=result.answer_text,
        citations=result.citations,
        grounded_in=result.grounded_in,
    )


@router.get("/status", response_model=StatusResponse)
async def retrieval_status() -> StatusResponse:
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "ok"
    except (RuntimeError, asyncpg.PostgresError) as exc:
        db_status = f"unavailable: {exc}"

    last_report = None
    if _EVAL_REPORT_PATH.exists():
        try:
            last_report = json.loads(_EVAL_REPORT_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Failed to read %s: %s", _EVAL_REPORT_PATH, exc)

    return StatusResponse(database=db_status, last_eval_report=last_report)
