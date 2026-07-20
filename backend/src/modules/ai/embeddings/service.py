"""
Embedding service — process_embedding_job() fetches one persisted decision,
builds its searchable text, embeds it via Voyage, and upserts the result
into public.decision_embeddings.

Runs after modules.ai.pipeline.service.process_and_persist_event() has
already committed the decision and enqueued an EmbeddingJob carrying only
tenant_id and decision_id — this module re-fetches the decision content
itself, so no decision text ever crosses the queue. Only
decision_statement, rationale, and alternatives_considered are read from
public.decisions; raw_content, permission_scope, actor ids, and every other
decision column are never fetched, embedded, or logged.

Both the fetch and the upsert run inside tenant_conn(pool, tenant_id) - RLS
Layer 1 plus the explicit tenant_id predicate below - and the fetched row
is checked with assert_tenant_scope() (Layer 2) before its text is ever
embedded, matching every other tenant-table access path in this codebase.
"""
from __future__ import annotations

import logging

import asyncpg

from common.config.voyage_config import get_voyage_config
from database.tenant_connection import tenant_conn
from modules.ai.embeddings.provider import embed_document
from modules.ai.embeddings.schemas import DecisionEmbeddingInput, DecisionEmbeddingResult
from modules.security.tenant_guard import assert_tenant_scope
from queues.pgmq.schemas import EmbeddingJob

log = logging.getLogger(__name__)


class EmbeddingProcessingError(Exception):
    """Base class for all process_embedding_job() failures raised by this service."""


class DecisionNotFoundError(EmbeddingProcessingError):
    """No public.decisions row matches (decision_id, tenant_id) — non-retryable.

    The fetch filters on both decision_id and tenant_id, so this also covers
    a tenant mismatch: a decision that exists under a different tenant_id
    than job.tenant_id looks identical to a missing decision, which is the
    correct behavior for multi-tenant isolation (never confirm or deny that
    a decision_id exists for someone else's tenant).
    """


class EmbeddingPersistenceError(EmbeddingProcessingError):
    """The upsert into public.decision_embeddings failed."""


def _build_searchable_text(
    decision_statement: str, rationale: str | None, alternatives_considered: list[str]
) -> str:
    """Deterministic embedding input text — never includes raw_content or metadata."""
    lines = [f"Decision: {decision_statement}"]
    if rationale:
        lines.append(f"Rationale: {rationale}")
    if alternatives_considered:
        lines.append(f"Alternatives considered: {', '.join(alternatives_considered)}")
    return "\n".join(lines)


def _format_vector_literal(embedding: list[float]) -> str:
    """pgvector text input format, e.g. "[0.1,0.2,-0.3]" — bound as a query param and cast via ::vector."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


async def process_embedding_job(pool: asyncpg.Pool, job: EmbeddingJob) -> None:
    """Fetch, embed, and persist one decision's embedding.

    Raises DecisionNotFoundError if no public.decisions row matches
    (job.decision_id, job.tenant_id). Raises whatever embed_document()
    raises (VoyageConfigError / VoyageEmbeddingError /
    VoyageResponseValidationError) if embedding fails. Raises
    EmbeddingPersistenceError if the upsert fails. The upsert is an
    idempotent ON CONFLICT (decision_id) DO UPDATE, so retrying this
    function for the same decision never creates a duplicate row.
    """
    async with tenant_conn(pool, job.tenant_id) as conn:
        row = await conn.fetchrow(
            """
            SELECT tenant_id, decision_statement, rationale, alternatives_considered
            FROM decisions
            WHERE id = $1 AND tenant_id = $2
            """,
            job.decision_id,
            job.tenant_id,
        )

        if row is None:
            raise DecisionNotFoundError(
                f"No decision found for decision_id={job.decision_id} tenant_id={job.tenant_id}"
            )
        assert_tenant_scope(row["tenant_id"], job.tenant_id)

        decision_input = DecisionEmbeddingInput(
            tenant_id=job.tenant_id,
            decision_id=job.decision_id,
            searchable_text=_build_searchable_text(
                row["decision_statement"],
                row["rationale"],
                list(row["alternatives_considered"] or []),
            ),
        )

        embedding = await embed_document(decision_input.searchable_text)

        config = get_voyage_config()
        result = DecisionEmbeddingResult(
            decision_id=job.decision_id,
            tenant_id=job.tenant_id,
            embedding=embedding,
            embedding_model=config.voyage_model,
            dimension=len(embedding),
        )

        try:
            await conn.execute(
                """
                INSERT INTO decision_embeddings (
                    decision_id, tenant_id, embedding, embedding_model, embedded_at
                ) VALUES ($1, $2, $3::vector, $4, now())
                ON CONFLICT (decision_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model,
                    embedded_at = EXCLUDED.embedded_at
                """,
                result.decision_id,
                result.tenant_id,
                _format_vector_literal(result.embedding),
                result.embedding_model,
            )
        except asyncpg.PostgresError as exc:
            raise EmbeddingPersistenceError(
                f"Failed to upsert embedding for decision_id={job.decision_id}: {exc}"
            ) from exc

    log.info(
        "Embedded decision id=%s model=%s dimension=%d",
        job.decision_id, result.embedding_model, result.dimension,
    )
