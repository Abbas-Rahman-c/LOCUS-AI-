"""
Search Service — orchestrates the full production pipeline:

    authenticated TenantContext
    -> query embedding
    -> tenant-scoped vector Top-K (RLS, via tenant_conn)
    -> permission-scope filtering (Layer 2)
    -> context building
    -> Claude answering
    -> citation validation

Every stage is reused as-is from its own module - this service duplicates
no embedding, search, permission, formatting, or Claude-calling logic; it
only sequences the existing functions and shapes their combined output
into one SearchResponse. tenant_id must already be authenticated and
validated (via app.dependencies.get_current_tenant) before it ever reaches
this function - never accepted from a request body.

permission_scopes is also never accepted from a request body: it is
authorization data, resolved server-side by the router via
modules.permissions.scope_resolver.resolve_permission_scopes(ctx) from the
authenticated TenantContext alone, before this function is ever called.
This function treats it as an opaque, already-resolved parameter and
applies it exactly as Phase 2's Layer 2 always has - it neither knows nor
cares how the caller derived it.
"""
from __future__ import annotations

import logging
import uuid

import asyncpg

from modules.answering.service import generate_answer
from modules.context.schemas import AuthorizedDecisionInput
from modules.context.service import build_context
from modules.permissions.service import filter_accessible_decisions
from modules.retrieval.vector.schemas import RetrievalMatch
from modules.retrieval.vector.service import search as vector_search
from modules.search.schemas import SearchMetadata, SearchResponse, SourceCitation

log = logging.getLogger(__name__)


def _to_context_input(match: RetrievalMatch) -> AuthorizedDecisionInput:
    """Adapt one authorized RetrievalMatch into the context builder's input shape.

    rationale/alternatives_considered/created_at/decision_type/owner flow
    straight through from the vector repository's query - only ever
    omitted when the underlying public.decisions row genuinely has no
    value, never fabricated.
    """
    return AuthorizedDecisionInput(
        decision_statement=match.decision_statement,
        rationale=match.rationale,
        alternatives=list(match.alternatives_considered),
        confidence=match.confidence,
        created_at=match.created_at.isoformat() if match.created_at else None,
        decision_type=match.decision_type,
        owner=match.owner,
    )


def _build_citations(
    citation_numbers: list[int], authorized: list[RetrievalMatch]
) -> list[SourceCitation]:
    """Map Claude's cited decision numbers back to the authorized decision at
    that position.

    ContextService.build_context() numbers decisions 1-indexed in exactly
    the order it's given, so decision N is authorized[N-1]. A citation
    number outside that range is skipped, never fabricated into a fake
    decision - this is the citation *validation* step: only numbers that
    resolve to a real, authorized decision ever become a SourceCitation.
    """
    citations = []
    for number in citation_numbers:
        if 1 <= number <= len(authorized):
            match = authorized[number - 1]
            citations.append(
                SourceCitation(
                    decision_number=number,
                    decision_id=match.decision_id,
                    decision_statement=match.decision_statement,
                    confidence=match.confidence,
                )
            )
    return citations


async def search(
    pool: asyncpg.Pool,
    tenant_id: uuid.UUID | str,
    question: str,
    permission_scopes: list[str],
    top_k: int,
) -> SearchResponse:
    """Run the full production pipeline and return the final SearchResponse.

    tenant_id must already be authenticated (from TenantContext) - this
    function never validates it against anything and never accepts it
    from request input; that trust boundary is the router's job.
    """
    matches, _embedding_dimension = await vector_search(pool, tenant_id, question, top_k)
    authorized = filter_accessible_decisions(permission_scopes, matches)
    context_result = build_context([_to_context_input(m) for m in authorized])
    answer_result = await generate_answer(question, context_result.context)

    citations = _build_citations(answer_result.citations, authorized)

    log.info(
        "Search: question=%r retrieved_count=%d authorized_count=%d decision_count=%d "
        "token_estimate=%d model=%s latency_ms=%.3f",
        question,
        len(matches),
        len(authorized),
        context_result.decision_count,
        context_result.token_estimate,
        answer_result.model,
        answer_result.latency_ms,
    )

    return SearchResponse(
        answer=answer_result.answer,
        citations=citations,
        metadata=SearchMetadata(
            model=answer_result.model,
            latency_ms=answer_result.latency_ms,
            retrieved_count=len(matches),
            authorized_count=len(authorized),
            decision_count=context_result.decision_count,
            token_estimate=context_result.token_estimate,
        ),
    )
