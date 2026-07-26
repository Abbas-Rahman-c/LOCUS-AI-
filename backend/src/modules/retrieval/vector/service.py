"""
Vector Retrieval Service — orchestrates question -> retrieval -> candidate
matches, per the configured RETRIEVAL_MODE.

Three modes (env var RETRIEVAL_MODE, default "hybrid_rrf"):
  - "semantic_only": vector search only (search_similar_decisions()).
  - "keyword_only": Postgres full-text search only
    (search_decisions_keyword()) - zero Voyage calls.
  - "hybrid_rrf": both run independently, then fused via Reciprocal Rank
    Fusion (modules.retrieval.reranking.rrf.fuse_rrf(), k=60).

"Smarter retrieval": this function now fetches candidate_k candidates
(default DEFAULT_CANDIDATE_K=20), not just top_k - the return list is the
deduplicated candidate pool, NOT truncated to top_k. Truncation to the
final top_k happens downstream, after permission filtering, via the
cross-encoder reranker (modules.retrieval.reranking.cross_encoder.rerank())
in modules.search.service - retrieving broadly and reranking narrowly
produces better final-top-5 precision than asking the DB's cosine/FTS
ranking alone to be precise at top_k=5. top_k is still accepted (as a
floor: candidate_k is never smaller than top_k) so any caller that doesn't
rerank still gets a sensibly-sized, top_k-or-larger list back.

retrieval_query lets the caller pass a query-understanding-rewritten
string (see modules.query_understanding) to embed/full-text-search
INSTEAD OF the raw question, while `question` is still logged/passed
through for callers that need the original text. Falls back to `question`
whenever retrieval_query is None or blank.

No permission-scope filtering, context building, or Claude answering
happen here - this is retrieval only, computed entirely inside the
authenticated tenant. See modules/search/service.py for the full
orchestration this feeds into.
"""
from __future__ import annotations

import logging
import os
import time
import uuid

import asyncpg

from modules.retrieval.reranking.rrf import DEFAULT_RRF_K, fuse_rrf
from modules.retrieval.vector.keyword_repository import search_decisions_keyword
from modules.retrieval.vector.query_embedding import generate_query_embedding
from modules.retrieval.vector.repository import search_similar_decisions
from modules.retrieval.vector.schemas import DEFAULT_CANDIDATE_K, DEFAULT_TOP_K, RetrievalMatch

log = logging.getLogger(__name__)

RETRIEVAL_MODES = {"semantic_only", "keyword_only", "hybrid_rrf"}
DEFAULT_RETRIEVAL_MODE = "hybrid_rrf"


def _dedup(matches: list[RetrievalMatch]) -> list[RetrievalMatch]:
    """Deduplicate by decision_id, preserving order, first occurrence wins.

    Defensive: fuse_rrf() already dedups internally, and semantic_only/
    keyword_only each return distinct decision_id rows straight from SQL,
    so this is normally a no-op - but it makes "no duplicate candidates
    reach the reranker" an explicit, checkable guarantee rather than an
    implicit one.
    """
    seen: set[uuid.UUID] = set()
    deduped = []
    for match in matches:
        if match.decision_id in seen:
            continue
        seen.add(match.decision_id)
        deduped.append(match)
    return deduped


def get_retrieval_mode() -> str:
    """Validate and return the configured retrieval mode.

    Same pattern as get_triage_model()/get_extraction_model(): an
    environment variable with a validated, explicit allowed set and a
    safe default, read fresh on every call (never cached), so changing
    RETRIEVAL_MODE takes effect on process restart without any code
    change.
    """
    mode = os.environ.get("RETRIEVAL_MODE", DEFAULT_RETRIEVAL_MODE)
    if mode not in RETRIEVAL_MODES:
        raise RuntimeError(
            f"RETRIEVAL_MODE '{mode}' is not one of {sorted(RETRIEVAL_MODES)}"
        )
    return mode


async def search(
    pool: asyncpg.Pool,
    tenant_id: uuid.UUID | str,
    question: str,
    top_k: int = DEFAULT_TOP_K,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    embedding_query: str | None = None,
    keyword_query: str | None = None,
) -> tuple[list[RetrievalMatch], int]:
    """Run question -> retrieval (per RETRIEVAL_MODE) -> deduplicated candidate matches.

    embedding_query and keyword_query let the caller drive the two
    retrieval channels independently (see modules.query_understanding):
    embedding_query should stay the raw natural-language question - a
    keyword-expanded rewrite (e.g. "Marcus Webb projects work assignments
    tasks") dilutes the embedding vector away from the specific entity/
    ticket-ID/filename it's supposed to match, and semantic search doesn't
    need AND/OR query construction help the way full-text search does.
    keyword_query is where a rewritten, OR-joined query string helps -
    websearch_to_tsquery() ANDs every term in its input, so trimming the
    question down to just its high-signal keywords (OR-joined) measurably
    improves keyword-channel recall. Both default to `question` when
    omitted or blank, reproducing the original single-query behavior.

    Returns (matches, embedding_dimension) - dimension is 0 for
    keyword_only, since no embedding is ever generated in that mode.
    `matches` has up to max(candidate_k, top_k) entries, deduplicated by
    decision_id - callers that want a final top_k should rerank/truncate
    it themselves (see modules.search.service). Raises whatever the
    underlying retrieval call(s) raise: VoyageConfigError, ValueError
    (blank question, bad top_k/embedding), VoyageEmbeddingError,
    VoyageResponseValidationError, or an asyncpg.PostgresError from the DB.
    """
    mode = get_retrieval_mode()
    start = time.perf_counter()

    fetch_k = max(candidate_k, top_k)
    effective_embedding_query = (embedding_query or "").strip() or question
    effective_keyword_query = (keyword_query or "").strip() or question

    if mode == "semantic_only":
        embedding = await generate_query_embedding(effective_embedding_query)
        matches = await search_similar_decisions(pool, tenant_id, embedding, fetch_k)
        dimension = len(embedding)

    elif mode == "keyword_only":
        matches = await search_decisions_keyword(pool, tenant_id, effective_keyword_query, fetch_k)
        dimension = 0

    else:  # hybrid_rrf
        embedding = await generate_query_embedding(effective_embedding_query)
        vector_matches = await search_similar_decisions(pool, tenant_id, embedding, fetch_k)
        keyword_matches = await search_decisions_keyword(pool, tenant_id, effective_keyword_query, fetch_k)
        matches = fuse_rrf(vector_matches, keyword_matches, top_k=fetch_k, k=DEFAULT_RRF_K)
        dimension = len(embedding)

    matches = _dedup(matches)

    elapsed_ms = (time.perf_counter() - start) * 1000
    log.info(
        "Retrieval: mode=%s question=%r embedding_query=%r keyword_query=%r candidate_k=%d "
        "result_count=%d retrieval_time_ms=%.3f",
        mode,
        question,
        effective_embedding_query if embedding_query else None,
        effective_keyword_query if keyword_query else None,
        fetch_k,
        len(matches),
        elapsed_ms,
    )

    return matches, dimension
