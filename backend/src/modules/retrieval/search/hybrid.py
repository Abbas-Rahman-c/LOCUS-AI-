"""
Hybrid search — full-text search over decisions with mandatory tenant scoping.

Architecture:
  - Accepts a text query and returns matching decisions.
  - The WHERE clause ALWAYS includes tenant_id (explicit application filter).
  - Every returned row is checked via assert_tenant_scope() (Layer 2).
  - Layer 1 (RLS) is engaged automatically via tenant_conn().

Vector/embedding search is scaffolded but not activated for MVP — the
decision_embeddings table exists but no embedding pipeline is live yet.
The full-text path is the one exercised in production and in tests.
"""
from __future__ import annotations

import logging
import uuid

import asyncpg

from database.tenant_connection import tenant_conn
from modules.decisions.schemas import DecisionOut
from modules.security.tenant_guard import assert_tenant_scope

log = logging.getLogger(__name__)


async def search_decisions(
    query: str,
    tenant_id: uuid.UUID | str,
    pool: asyncpg.Pool,
    limit: int = 10,
) -> list[DecisionOut]:
    """
    Full-text search over decisions scoped to tenant_id.

    Both Layer 1 (RLS via tenant_conn) and Layer 2 (assert_tenant_scope per row)
    are applied.  The SQL WHERE clause also includes an explicit tenant_id
    predicate as a belt-and-suspenders measure independent of RLS.

    Returns an empty list when no results match — never raises on "no results".
    """
    tenant_id = uuid.UUID(str(tenant_id))
    query = query.strip()

    if not query:
        return []

    async with tenant_conn(pool, tenant_id) as conn:
        rows = await conn.fetch(
            """
            SELECT id, tenant_id, record_type, decision_statement, rationale,
                   status, scope, confidence, created_at, updated_at,
                   ts_rank(
                       to_tsvector('english', decision_statement || ' ' || COALESCE(rationale, '')),
                       plainto_tsquery('english', $1)
                   ) AS rank
            FROM decisions
            WHERE tenant_id = $2
              AND to_tsvector('english', decision_statement || ' ' || COALESCE(rationale, ''))
                  @@ plainto_tsquery('english', $1)
            ORDER BY rank DESC, created_at DESC
            LIMIT $3
            """,
            query,
            tenant_id,
            limit,
        )

    results = []
    for row in rows:
        # Layer 2: independently verify each row's tenant
        assert_tenant_scope(row["tenant_id"], tenant_id)
        results.append(DecisionOut.model_validate({k: v for k, v in dict(row).items() if k != "rank"}))

    log.info(
        "search_decisions: query=%r tenant=%s hits=%d",
        query,
        tenant_id,
        len(results),
    )
    return results
