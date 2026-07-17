"""
MCP tool: get_decision_context

Fetches a single decision and its source links for use in AI context windows.
Applies the same dual-layer tenant isolation as the UI path.
"""
from __future__ import annotations

import logging
import uuid

import asyncpg

from app.dependencies import TenantContext
from database.tenant_connection import tenant_conn
from modules.security.tenant_guard import assert_tenant_scope

log = logging.getLogger(__name__)


async def get_decision_context_tool(
    params: dict,
    ctx: TenantContext,
    pool: asyncpg.Pool,
) -> dict:
    """
    MCP tool handler for 'get_decision_context'.

    Expected params: { "decision_id": str (UUID) }

    Returns the decision record + its source permalinks.
    Returns { "error": "not found" } when the decision does not exist or belongs
    to another tenant — existence is NOT revealed to the caller.
    """
    decision_id_str: str = params.get("decision_id", "")

    try:
        decision_id = uuid.UUID(decision_id_str)
    except (ValueError, AttributeError):
        return {"error": "decision_id must be a valid UUID"}

    tenant_id = uuid.UUID(ctx.tenant_id)

    async with tenant_conn(pool, tenant_id) as conn:
        # Fetch decision — explicit tenant_id in WHERE (Layer 2 belt-and-suspenders)
        row = await conn.fetchrow(
            """
            SELECT id, tenant_id, record_type, decision_statement, rationale,
                   status, scope, confidence, created_at, updated_at
            FROM decisions
            WHERE id = $1 AND tenant_id = $2
            """,
            decision_id,
            tenant_id,
        )

        if row is None:
            return {"error": "not found"}

        # Layer 2 application pre-filter
        assert_tenant_scope(row["tenant_id"], tenant_id)

        # Fetch sources for this decision
        source_rows = await conn.fetch(
            """
            SELECT permalink, created_at
            FROM decision_sources
            WHERE decision_id = $1 AND tenant_id = $2
            ORDER BY created_at ASC
            """,
            decision_id,
            tenant_id,
        )
        # Layer 2 on sources too
        for src in source_rows:
            assert_tenant_scope(row["tenant_id"], tenant_id)  # decision tenant checked above

    return {
        "decision": {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "record_type": row["record_type"],
            "decision_statement": row["decision_statement"],
            "rationale": row["rationale"],
            "status": row["status"],
            "scope": row["scope"],
            "confidence": float(row["confidence"]),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        },
        "sources": [
            {"permalink": src["permalink"], "cited_at": src["created_at"].isoformat()}
            for src in source_rows
        ],
    }
