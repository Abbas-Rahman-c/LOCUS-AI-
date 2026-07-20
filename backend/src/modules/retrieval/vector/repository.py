"""
Vector Retrieval Repository — top-K cosine similarity search over
public.decision_embeddings, joined with public.decisions, computed entirely
inside one tenant's RLS-scoped transaction.

Layer 1: RLS policies (tenant_isolation_decisions / tenant_isolation_
decision_embeddings), engaged by running the whole query inside
tenant_conn(pool, tenant_id) - this sets app.current_tenant_id for the
transaction, so both tables are restricted to that tenant before the
planner ever sees a row.
Layer 2: assert_tenant_scope() re-checked on every returned row, so a
misconfigured connection (RLS never engaged) fails closed and loud rather
than silently returning cross-tenant data.

This module never performs a global, cross-tenant query and filters
afterward in Python - top_k is computed within the authenticated tenant,
full stop. The explicit `d.tenant_id = $2` predicate below is redundant
with RLS by design (defense-in-depth + lets the planner use
idx_decisions_tenant_status instead of relying solely on the RLS rewrite).
"""
from __future__ import annotations

import uuid

import asyncpg

from database.tenant_connection import tenant_conn
from modules.retrieval.vector.schemas import (
    MAX_TOP_K,
    REQUIRED_EMBEDDING_DIMENSION,
    RetrievalMatch,
)
from modules.security.tenant_guard import assert_tenant_scope


def _format_vector_literal(embedding: list[float]) -> str:
    """pgvector text input format, e.g. "[0.1,0.2,-0.3]" — bound as a query param and cast via ::vector."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _validate_top_k(top_k: int) -> None:
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise ValueError(f"top_k must be an int, got {type(top_k).__name__}")
    if not (1 <= top_k <= MAX_TOP_K):
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}, got {top_k}")


def _validate_embedding(embedding: list[float]) -> None:
    if not isinstance(embedding, list) or len(embedding) != REQUIRED_EMBEDDING_DIMENSION:
        got = len(embedding) if isinstance(embedding, list) else type(embedding).__name__
        raise ValueError(
            f"embedding must be a list of exactly {REQUIRED_EMBEDDING_DIMENSION} floats, "
            f"got {got!r} - this must match public.decision_embeddings.embedding's "
            "vector(1024) column and the HNSW index built on it"
        )


async def search_similar_decisions(
    pool: asyncpg.Pool,
    tenant_id: uuid.UUID | str,
    embedding: list[float],
    top_k: int,
) -> list[RetrievalMatch]:
    """Return the top_k decisions nearest to embedding, within tenant_id only.

    Uses pgvector's `<=>` operator (cosine distance, matching the HNSW
    index idx_decision_embeddings_vec built with vector_cosine_ops) -
    identical operator/index usage to any prior non-tenant-scoped version,
    so no index rebuild is required. similarity_score is
    1 - cosine_distance, so 1.0 is an identical vector and lower values are
    less similar.

    Raises ValueError if top_k or embedding fail validation. Every row is
    passed through assert_tenant_scope() before being returned; a
    TenantScopeError there means RLS did not actually engage on this
    connection - a bug to fix, never a case to silently work around.
    """
    _validate_top_k(top_k)
    _validate_embedding(embedding)

    tenant_uuid = uuid.UUID(str(tenant_id))
    vector_literal = _format_vector_literal(embedding)

    async with tenant_conn(pool, tenant_uuid) as conn:
        rows = await conn.fetch(
            """
            SELECT
                d.id AS decision_id,
                d.decision_statement,
                1 - (de.embedding <=> $1::vector) AS similarity_score,
                d.confidence,
                d.tenant_id,
                d.permission_scope,
                d.rationale,
                d.alternatives_considered,
                d.created_at,
                d.record_type AS decision_type,
                (
                    SELECT COALESCE(a.display_name, a.email)
                    FROM public.decision_actors da
                    JOIN public.actors a
                      ON a.id = da.actor_id AND a.tenant_id = d.tenant_id
                    WHERE da.decision_id = d.id
                      AND da.tenant_id = d.tenant_id
                      AND da.role = 'decided_by'
                    LIMIT 1
                ) AS owner
            FROM public.decision_embeddings de
            JOIN public.decisions d ON d.id = de.decision_id AND d.tenant_id = de.tenant_id
            WHERE d.tenant_id = $2
            ORDER BY de.embedding <=> $1::vector ASC
            LIMIT $3
            """,
            vector_literal,
            tenant_uuid,
            top_k,
        )

    matches = []
    for row in rows:
        assert_tenant_scope(row["tenant_id"], tenant_uuid)
        matches.append(
            RetrievalMatch(
                decision_id=row["decision_id"],
                decision_statement=row["decision_statement"],
                similarity_score=float(row["similarity_score"]),
                confidence=float(row["confidence"]),
                tenant_id=row["tenant_id"],
                permission_scope=list(row["permission_scope"] or []),
                rationale=row["rationale"],
                alternatives_considered=list(row["alternatives_considered"] or []),
                created_at=row["created_at"],
                decision_type=row["decision_type"],
                owner=row["owner"],
            )
        )
    return matches
