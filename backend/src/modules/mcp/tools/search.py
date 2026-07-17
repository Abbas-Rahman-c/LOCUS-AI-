"""
MCP tool: search_decisions

Wraps the hybrid search function as an MCP-callable tool.
The tenant context is extracted from the validated JWT — MCP clients must
supply the same Bearer token as UI clients.  No special MCP-only bypass exists.
"""
from __future__ import annotations

import logging

import asyncpg

from app.dependencies import TenantContext
from modules.retrieval.search.hybrid import search_decisions

log = logging.getLogger(__name__)


async def search_decisions_tool(
    params: dict,
    ctx: TenantContext,
    pool: asyncpg.Pool,
) -> dict:
    """
    MCP tool handler for 'search_decisions'.

    Expected params: { "query": str, "limit"?: int }

    Returns: { "decisions": [ { decision fields... } ] }
    """
    query: str = params.get("query", "").strip()
    limit: int = int(params.get("limit", 10))
    limit = max(1, min(limit, 50))  # clamp

    if not query:
        return {"decisions": [], "error": "query is required"}

    results = await search_decisions(query=query, tenant_id=ctx.tenant_id, pool=pool, limit=limit)

    return {
        "decisions": [d.model_dump(mode="json") for d in results],
        "total": len(results),
        "tenant_id": ctx.tenant_id,
    }
