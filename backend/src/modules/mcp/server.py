"""
MCP-compatible tool server (read-only for MVP).

Dispatches an MCPToolRequest to the matching function in modules.mcp.tools,
times it, and logs the call to public.mcp_tool_calls (tool_name,
request_params, result_decision_ids, latency_ms) -- the audit trail
migration 003's mcp_tool_calls table exists for. Logging failures are
swallowed (logged, not raised): an MCP client should get its search
results even if the audit-log insert has a transient failure.
"""
from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

import asyncpg

from database.pool import get_db_pool
from modules.mcp.schemas import MCPToolRequest, MCPToolResponse
from modules.mcp.tools.context import get_decision_context
from modules.mcp.tools.search import search_decisions
from modules.security.tenant_guard import set_current_tenant_id

log = logging.getLogger(__name__)


class UnknownToolError(Exception):
    """Raised when request.tool_name doesn't match a registered tool."""


async def _run_search_decisions(tenant_id: UUID, params: dict[str, Any]) -> tuple[dict, list[UUID]]:
    results = await search_decisions(
        tenant_id, params["query"], top_k=params.get("top_k", 10)
    )
    decision_ids = [UUID(r["decision_id"]) for r in results]
    return {"results": results}, decision_ids


async def _run_get_decision_context(tenant_id: UUID, params: dict[str, Any]) -> tuple[dict, list[UUID]]:
    decision_id = UUID(params["decision_id"])
    context = await get_decision_context(tenant_id, decision_id)
    return context, [decision_id]


_TOOL_REGISTRY = {
    "search_decisions": _run_search_decisions,
    "get_decision_context": _run_get_decision_context,
}


async def _log_tool_call(
    pool: asyncpg.Pool,
    request: MCPToolRequest,
    result_decision_ids: list[UUID],
    latency_ms: int,
) -> None:
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await set_current_tenant_id(conn, request.tenant_id)
                await conn.execute(
                    """
                    INSERT INTO public.mcp_tool_calls (
                        tenant_id, requesting_client, tool_name, request_params,
                        result_decision_ids, latency_ms
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    request.tenant_id,
                    request.requesting_client,
                    request.tool_name,
                    request.params,
                    result_decision_ids,
                    latency_ms,
                )
    except asyncpg.PostgresError:
        log.exception("Failed to log mcp_tool_calls row for tool_name=%s", request.tool_name)


async def handle_tool_call(
    request: MCPToolRequest, *, pool: asyncpg.Pool | None = None
) -> MCPToolResponse:
    handler = _TOOL_REGISTRY.get(request.tool_name)
    if handler is None:
        raise UnknownToolError(f"Unknown MCP tool: {request.tool_name!r}")

    db_pool = pool if pool is not None else get_db_pool()

    start = time.monotonic()
    result, result_decision_ids = await handler(request.tenant_id, request.params)
    latency_ms = int((time.monotonic() - start) * 1000)

    await _log_tool_call(db_pool, request, result_decision_ids, latency_ms)

    return MCPToolResponse(
        tool_name=request.tool_name,
        result=result,
        result_decision_ids=result_decision_ids,
        latency_ms=latency_ms,
    )
