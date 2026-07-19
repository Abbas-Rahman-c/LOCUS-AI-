"""
Hybrid retrieval: pgvector cosine similarity + Postgres full-text search,
run in parallel, each leg tenant-scoped and returned as its own ranked
list for modules.retrieval.reranking.rrf to fuse.

Deliberately does NOT fuse or resolve permalinks itself -- that split
(hybrid finds candidates, rrf merges them, resolver looks up permalinks
only for the final set) keeps each module doing one thing, and means
resolver.py's DB round-trip only ever runs for top_k decisions, not every
candidate either leg considered.

Both legs query public.decisions directly:
  - vector leg joins public.decision_embeddings and orders by the pgvector
    `<=>` cosine-distance operator, matching the HNSW
    (vector_cosine_ops) index from migration 007. A decision with no
    embedding yet (decision_embeddings has no row) simply cannot appear
    in vector results -- it can still surface via the keyword leg.
  - keyword leg uses to_tsvector('english', decision_statement || ' ' ||
    rationale) @@ plainto_tsquery(...), matching idx_decisions_fts's exact
    expression from migration 003 so Postgres can use that GIN index
    instead of a sequential scan.

Every query carries an explicit tenant_id predicate (modules.security.
tenant_guard's "pre-filter" layer) in addition to setting the RLS GUC
(the "RLS" layer) -- see tenant_guard.py's docstring for why both matter.
"""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import asyncpg

from database.pool import get_db_pool
from modules.ai.embeddings.provider import (
    VoyageConfigError,
    VoyageEmbeddingError,
    VoyageResponseValidationError,
    embed_query,
)
from modules.retrieval.schemas import RetrievedDecision
from modules.security.tenant_guard import set_current_tenant_id

log = logging.getLogger(__name__)

# Each leg over-fetches relative to the final top_k the caller wants, so RRF
# (which rewards a candidate appearing near the top of *either* list) has a
# meaningful pool to fuse rather than two already-truncated top-10s.
DEFAULT_CANDIDATE_MULTIPLIER = 4
MIN_CANDIDATE_POOL = 25


class HybridSearchError(Exception):
    """Base class for hybrid_search() failures."""


class VectorLegError(HybridSearchError):
    """The vector (pgvector cosine) leg failed -- embedding or DB error."""


class KeywordLegError(HybridSearchError):
    """The keyword (Postgres full-text search) leg failed."""


def _candidate_pool_size(top_k: int) -> int:
    return max(top_k * DEFAULT_CANDIDATE_MULTIPLIER, MIN_CANDIDATE_POOL)


def _vector_literal(embedding: list[float]) -> str:
    """pgvector text input format, e.g. "[0.1,0.2,-0.3]" -- bound as a query
    param and cast via ::vector. Mirrors
    modules.ai.embeddings.service._format_vector_literal (kept as a
    separate copy rather than a shared import: that module owns the
    embedding *write* path, this one only ever reads)."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _row_to_decision(row: asyncpg.Record, *, vector_rank: int | None = None,
                      vector_score: float | None = None, keyword_rank: int | None = None,
                      keyword_score: float | None = None) -> RetrievedDecision:
    return RetrievedDecision(
        decision_id=row["id"],
        tenant_id=row["tenant_id"],
        decision_statement=row["decision_statement"],
        rationale=row["rationale"],
        status=row["status"],
        record_type=row["record_type"],
        vector_rank=vector_rank,
        vector_score=vector_score,
        keyword_rank=keyword_rank,
        keyword_score=keyword_score,
    )


async def _vector_leg(
    pool: asyncpg.Pool, tenant_id: UUID, query_text: str, limit: int
) -> list[RetrievedDecision]:
    try:
        query_embedding = await embed_query(query_text)
    except (VoyageConfigError, VoyageEmbeddingError, VoyageResponseValidationError, ValueError) as exc:
        raise VectorLegError(f"Failed to embed query for vector search: {exc}") from exc

    vector_param = _vector_literal(query_embedding)

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await set_current_tenant_id(conn, tenant_id)
                rows = await conn.fetch(
                    """
                    SELECT
                        d.id, d.tenant_id, d.decision_statement, d.rationale,
                        d.status, d.record_type,
                        1 - (e.embedding <=> $2::vector) AS cosine_similarity
                    FROM public.decisions d
                    JOIN public.decision_embeddings e
                        ON e.decision_id = d.id AND e.tenant_id = d.tenant_id
                    WHERE d.tenant_id = $1
                    ORDER BY e.embedding <=> $2::vector ASC
                    LIMIT $3
                    """,
                    tenant_id,
                    vector_param,
                    limit,
                )
    except asyncpg.PostgresError as exc:
        raise VectorLegError(f"Vector search query failed: {exc}") from exc

    return [
        _row_to_decision(row, vector_rank=i + 1, vector_score=float(row["cosine_similarity"]))
        for i, row in enumerate(rows)
    ]


async def _keyword_leg(
    pool: asyncpg.Pool, tenant_id: UUID, query_text: str, limit: int
) -> list[RetrievedDecision]:
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await set_current_tenant_id(conn, tenant_id)
                rows = await conn.fetch(
                    """
                    SELECT
                        d.id, d.tenant_id, d.decision_statement, d.rationale,
                        d.status, d.record_type,
                        ts_rank(
                            to_tsvector('english', d.decision_statement || ' ' || coalesce(d.rationale, '')),
                            plainto_tsquery('english', $2)
                        ) AS keyword_rank
                    FROM public.decisions d
                    WHERE d.tenant_id = $1
                        AND to_tsvector('english', d.decision_statement || ' ' || coalesce(d.rationale, ''))
                            @@ plainto_tsquery('english', $2)
                    ORDER BY keyword_rank DESC
                    LIMIT $3
                    """,
                    tenant_id,
                    query_text,
                    limit,
                )
    except asyncpg.PostgresError as exc:
        raise KeywordLegError(f"Keyword search query failed: {exc}") from exc

    return [
        _row_to_decision(row, keyword_rank=i + 1, keyword_score=float(row["keyword_rank"]))
        for i, row in enumerate(rows)
    ]


class HybridSearchLegs:
    """Both legs' ranked candidate lists, pre-fusion."""

    __slots__ = ("vector", "keyword")

    def __init__(self, vector: list[RetrievedDecision], keyword: list[RetrievedDecision]) -> None:
        self.vector = vector
        self.keyword = keyword


async def hybrid_search(
    query_text: str,
    tenant_id: UUID,
    top_k: int = 10,
    *,
    pool: asyncpg.Pool | None = None,
) -> HybridSearchLegs:
    """Runs the vector and keyword legs concurrently, tenant-scoped.

    Returns both ranked lists unmerged -- pass the result to
    modules.retrieval.reranking.rrf.reciprocal_rank_fusion() to get a single
    fused ranking. Raises VectorLegError / KeywordLegError (both subclasses
    of HybridSearchError) if either leg fails; a failure in one leg does not
    silently degrade to the other leg's results alone, since that would
    quietly change retrieval quality without surfacing why -- callers that
    want graceful degradation should catch the specific leg error them-
    selves and decide.
    """
    if tenant_id is None:
        raise ValueError("hybrid_search() requires a non-null tenant_id")
    if not query_text or not query_text.strip():
        raise ValueError("hybrid_search() query_text must not be blank")

    db_pool = pool if pool is not None else get_db_pool()
    limit = _candidate_pool_size(top_k)

    vector_results, keyword_results = await asyncio.gather(
        _vector_leg(db_pool, tenant_id, query_text, limit),
        _keyword_leg(db_pool, tenant_id, query_text, limit),
    )

    log.info(
        "hybrid_search tenant_id=%s vector_hits=%d keyword_hits=%d top_k=%d",
        tenant_id, len(vector_results), len(keyword_results), top_k,
    )

    return HybridSearchLegs(vector=vector_results, keyword=keyword_results)
