"""
search_decisions() MCP tool -- thin wrapper over modules.retrieval.pipeline.
RAGPipeline.retrieve(), reshaped into plain dicts (MCP tool results cross a
JSON-RPC boundary, so no pydantic/UUID objects survive past this module).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

from modules.retrieval.citations.resolver import resolve_permalinks
from modules.retrieval.pipeline import RAGPipeline


async def search_decisions(
    tenant_id: UUID,
    query: str,
    top_k: int = 10,
    *,
    pool: asyncpg.Pool | None = None,
) -> list[dict[str, Any]]:
    """Returns up to `top_k` ranked decisions for `query`, each with its
    resolved permalink, most-relevant first."""
    pipeline = RAGPipeline(pool=pool)
    retrieval = await pipeline.retrieve(query, tenant_id, top_k=top_k)

    permalinks = await resolve_permalinks(retrieval.decision_ids, tenant_id, pool=pool)

    return [
        {
            "decision_id": str(ranked.decision.decision_id),
            "decision_statement": ranked.decision.decision_statement,
            "rationale": ranked.decision.rationale,
            "status": ranked.decision.status,
            "record_type": ranked.decision.record_type,
            "permalink": permalinks.get(ranked.decision.decision_id),
            "rank": ranked.rank,
            "rrf_score": ranked.rrf_score,
        }
        for ranked in retrieval.ranked
    ]
