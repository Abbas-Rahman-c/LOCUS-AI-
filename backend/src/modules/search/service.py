"""
Search Service — orchestrates the full production pipeline:

    authenticated TenantContext
    -> query understanding (intent/entities/keywords/rewrite, 1 Claude tool call)
    -> tenant-scoped vector/keyword/hybrid candidate retrieval (top candidate_k, RLS)
    -> permission-scope filtering (Layer 2)
    -> cross-encoder reranking (candidate_k -> top_k, entity-boosted)
    -> structured context building
    -> Claude answering (forced tool call: answer/reasoning/citations/confidence)
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

Query understanding fails OPEN: if analyze_query() raises for any reason
(Claude API error, timeout, validation failure), this service logs a
warning and falls back to NULL_QUERY_ANALYSIS (which makes
retrieval_query/entities/is_multi_document all inert, so retrieval and
answering behave exactly as they did before this upgrade) rather than
failing the whole /search request over a query-understanding hiccup.
Permission filtering and the security-relevant retrieval path are
untouched by this fallback.
"""
from __future__ import annotations

import logging
import uuid

import asyncpg

from modules.answering.service import generate_answer
from modules.context.schemas import AuthorizedDecisionInput
from modules.context.service import build_context
from modules.permissions.service import filter_accessible_decisions
from modules.query_understanding.schemas import NULL_QUERY_ANALYSIS, QueryAnalysis
from modules.query_understanding.service import QueryAnalysisError, analyze_query
from modules.retrieval.reranking.cross_encoder import rerank
from modules.retrieval.vector.schemas import DEFAULT_CANDIDATE_K, MAX_TOP_K, RetrievalMatch
from modules.retrieval.vector.service import search as vector_search
from modules.search.schemas import SearchMetadata, SearchResponse, SourceCitation

log = logging.getLogger(__name__)

# When a question is detected as multi-document (e.g. "what decisions have
# we made about billing"), widen the final result count so a structured
# summary has more than one decision to draw on, without exceeding what
# the caller explicitly requested if they asked for more than this anyway.
MULTI_DOCUMENT_MIN_TOP_K = 10

# Reranker output floor (post-upgrade-benchmark tuning): the cross-encoder
# was dropping correctly-retrieved candidates below a top_k=5 cutoff on
# near-duplicate/topically-overlapping decisions - widening the window to
# 7 gives it more room before truncation without changing the model,
# candidate_k, or anything else. Multi-document's floor of 10 already
# exceeds this, so multi-document behavior is unaffected.
RERANK_MIN_TOP_K = 7


def _to_context_input(match: RetrievalMatch) -> AuthorizedDecisionInput:
    """Adapt one authorized RetrievalMatch into the context builder's input shape.

    rationale/alternatives_considered/created_at/decision_type/owner/source
    flow straight through from the vector repository's query - only ever
    omitted when the underlying public.decisions/raw_events row genuinely
    has no value, never fabricated. impact has no backing column today, so
    it is always None (see modules.context.schemas.AuthorizedDecisionInput).
    """
    return AuthorizedDecisionInput(
        decision_statement=match.decision_statement,
        rationale=match.rationale,
        alternatives=list(match.alternatives_considered),
        confidence=match.confidence,
        created_at=match.created_at.isoformat() if match.created_at else None,
        decision_type=match.decision_type,
        owner=match.owner,
        source=match.source,
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


async def _understand_query(question: str) -> QueryAnalysis:
    try:
        return await analyze_query(question)
    except QueryAnalysisError as exc:
        log.warning("Query understanding failed, falling back to raw question: %s", exc)
        return NULL_QUERY_ANALYSIS


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
    analysis = await _understand_query(question)

    effective_top_k = max(top_k, RERANK_MIN_TOP_K)
    if analysis.is_multi_document:
        effective_top_k = min(MAX_TOP_K, max(effective_top_k, MULTI_DOCUMENT_MIN_TOP_K))
    candidate_k = max(DEFAULT_CANDIDATE_K, effective_top_k * 2)

    candidates, _embedding_dimension = await vector_search(
        pool, tenant_id, question,
        top_k=effective_top_k,
        candidate_k=candidate_k,
        embedding_query=question,  # always embed the raw question, never the keyword rewrite
        keyword_query=analysis.keyword_search_query,  # OR-joined rewrite helps FTS only
    )

    # Permission filtering happens BEFORE reranking, on purpose: reranking
    # must never even see, score, or reorder a decision the caller isn't
    # authorized for. This preserves the exact security property Phase 2
    # always had - only the input list to filter_accessible_decisions()
    # is now the (larger) candidate pool instead of the final top_k.
    authorized_candidates = filter_accessible_decisions(permission_scopes, candidates)

    reranked = rerank(question, authorized_candidates, top_k=effective_top_k, entities=analysis.entities)

    context_result = build_context([_to_context_input(m) for m in reranked])
    answer_result = await generate_answer(question, context_result.context, analysis)

    citations = _build_citations(answer_result.citations, reranked)

    log.info(
        "Search: question=%r question_type=%s is_multi_document=%s candidate_count=%d "
        "authorized_count=%d reranked_count=%d decision_count=%d token_estimate=%d "
        "model=%s latency_ms=%.3f",
        question, analysis.question_type.value, analysis.is_multi_document, len(candidates),
        len(authorized_candidates), len(reranked), context_result.decision_count,
        context_result.token_estimate, answer_result.model, answer_result.latency_ms,
    )

    return SearchResponse(
        answer=answer_result.answer,
        citations=citations,
        reasoning=answer_result.reasoning,
        confidence=answer_result.confidence,
        metadata=SearchMetadata(
            model=answer_result.model,
            latency_ms=answer_result.latency_ms,
            retrieved_count=len(candidates),
            authorized_count=len(authorized_candidates),
            decision_count=context_result.decision_count,
            token_estimate=context_result.token_estimate,
            question_type=analysis.question_type.value,
            is_multi_document=analysis.is_multi_document,
            reranked=True,
        ),
    )
