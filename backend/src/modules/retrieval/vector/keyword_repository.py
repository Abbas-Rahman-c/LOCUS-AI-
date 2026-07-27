"""
Keyword Retrieval Repository — full-text search over public.decisions,
computed entirely inside one tenant's RLS-scoped transaction. Added
alongside repository.py's vector search (unmodified) to support hybrid
search (Reciprocal Rank Fusion) - this module never touches that file.

Uses the exact to_tsvector('english', decision_statement || ' ' ||
coalesce(rationale, '')) expression that idx_decisions_fts (migration 003)
is already built on, so this query hits that existing GIN index - no new
migration required. websearch_to_tsquery() (rather than plainto_tsquery())
is used for a more forgiving natural-language query parser, better suited
to /search's free-text questions than the MCP edge function's
search_decisions_fts() SQL function (migration 009), which this module
does not call or modify.

Same two-layer tenant isolation as search_similar_decisions(): RLS via
tenant_conn() (Layer 1) plus assert_tenant_scope() per row (Layer 2).
"""
from __future__ import annotations

import uuid

import asyncpg

from database.tenant_connection import tenant_conn
from modules.retrieval.vector.schemas import MAX_TOP_K, RetrievalMatch
from modules.security.tenant_guard import assert_tenant_scope


def _validate_top_k(top_k: int) -> None:
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise ValueError(f"top_k must be an int, got {type(top_k).__name__}")
    if not (1 <= top_k <= MAX_TOP_K):
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}, got {top_k}")


async def search_decisions_keyword(
    pool: asyncpg.Pool,
    tenant_id: uuid.UUID | str,
    question: str,
    top_k: int,
) -> list[RetrievalMatch]:
    """Return the top_k decisions matching question via Postgres full-text
    search, within tenant_id only.

    similarity_score on the returned RetrievalMatch holds the FTS ts_rank
    value for keyword-sourced matches - not a cosine similarity, and not
    directly comparable to search_similar_decisions()'s similarity_score.
    Fusion (modules.retrieval.reranking.rrf.fuse_rrf) combines these two
    result lists by RANK POSITION only, never by comparing raw scores
    across methods - exactly why RRF is the right fusion strategy here.

    Raises ValueError if top_k fails validation or question is blank.
    Every row is passed through assert_tenant_scope() before being
    returned, matching search_similar_decisions()'s Layer 2 guarantee.
    Returns an empty list when nothing matches - never raises on "no
    results" (a query with no keyword overlap is a normal outcome, not
    an error).
    """
    _validate_top_k(top_k)
    query_text = question.strip()
    if not query_text:
        raise ValueError("search_decisions_keyword() question must not be blank")

    tenant_uuid = uuid.UUID(str(tenant_id))

    async with tenant_conn(pool, tenant_uuid) as conn:
        rows = await conn.fetch(
            """
            SELECT
                d.id AS decision_id,
                d.decision_statement,
                ts_rank(
                    to_tsvector('english', d.decision_statement || ' ' || COALESCE(d.rationale, '')),
                    websearch_to_tsquery('english', $1)
                ) AS similarity_score,
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
                ) AS owner,
                r.source AS source
            FROM public.decisions d
            LEFT JOIN public.raw_events r
              ON r.id = d.origin_raw_event_id AND r.tenant_id = d.tenant_id
            WHERE d.tenant_id = $2
              AND to_tsvector('english', d.decision_statement || ' ' || COALESCE(d.rationale, ''))
                  @@ websearch_to_tsquery('english', $1)
            ORDER BY similarity_score DESC, d.created_at DESC
            LIMIT $3
            """,
            query_text,
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
                source=row["source"],
            )
        )
    return matches
