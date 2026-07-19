"""
get_decision_context() MCP tool -- fetches one decision by id (not a
retrieval query), for when a caller already has a decision_id (e.g. from a
prior search_decisions() call) and wants its full detail plus permalink.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

from database.pool import get_db_pool
from modules.retrieval.citations.resolver import resolve_permalinks
from modules.security.tenant_guard import set_current_tenant_id


class DecisionNotFoundError(Exception):
    """No public.decisions row matches (decision_id, tenant_id)."""


async def get_decision_context(
    tenant_id: UUID,
    decision_id: UUID,
    *,
    pool: asyncpg.Pool | None = None,
) -> dict[str, Any]:
    if tenant_id is None:
        raise ValueError("get_decision_context() requires a non-null tenant_id")
    db_pool = pool if pool is not None else get_db_pool()

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await set_current_tenant_id(conn, tenant_id)
            row = await conn.fetchrow(
                """
                SELECT id, decision_statement, rationale, alternatives_considered,
                       status, record_type, scope, confidence, created_at, updated_at
                FROM public.decisions
                WHERE id = $1 AND tenant_id = $2
                """,
                decision_id,
                tenant_id,
            )

    if row is None:
        raise DecisionNotFoundError(f"No decision {decision_id} for tenant {tenant_id}")

    permalinks = await resolve_permalinks([decision_id], tenant_id, pool=pool)

    return {
        "decision_id": str(row["id"]),
        "decision_statement": row["decision_statement"],
        "rationale": row["rationale"],
        "alternatives_considered": list(row["alternatives_considered"] or []),
        "status": row["status"],
        "record_type": row["record_type"],
        "scope": row["scope"],
        "confidence": float(row["confidence"]),
        "permalink": permalinks.get(decision_id),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
