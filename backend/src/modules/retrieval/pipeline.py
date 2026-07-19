"""
RAGPipeline -- the real, DB + Sonnet backed implementation of
modules.retrieval.protocol.RAGPipeline.

Wires the four pieces the rest of this package built independently:
    hybrid_search()      -> two ranked candidate lists (vector, keyword)
    fuse_hybrid_legs()    -> one RRF-fused ranking
    synthesize_answer()   -> a grounded, cited answer over that ranking

This is the module scripts/run_rag_eval.py swaps in for
modules.retrieval.evaluation.mock_pipeline.MockRAGPipeline once you're
ready to score real retrieval quality instead of the mock's guaranteed-
matches baseline. Nothing in modules.retrieval.evaluation.runner or
.metrics imports this module directly -- they only ever see the
RAGPipeline Protocol, so this file existing and being correct is the
whole swap.

Both the DB pool and the Anthropic client are injectable (default to the
process-wide singletons via get_db_pool()/get_anthropic_client() when not
passed) so tests can wire in fakes without any live DB or API key.
"""
from __future__ import annotations

from uuid import UUID

import anthropic
import asyncpg

from modules.retrieval.reranking.rrf import DEFAULT_RRF_K, fuse_hybrid_legs
from modules.retrieval.schemas import RetrievalResult, SynthesizedAnswer
from modules.retrieval.search.hybrid import hybrid_search
from modules.retrieval.synthesis.synthesizer import synthesize_answer


def _require_tenant_id(tenant_id: UUID | None) -> UUID:
    """Fail loudly at the call site rather than let a None tenant_id reach
    hybrid_search()/synthesize_answer() as a silently-unfiltered predicate."""
    if tenant_id is None:
        raise ValueError("A tenant_id is required for any retrieval query")
    return tenant_id


class RAGPipeline:
    """Real retrieval + synthesis pipeline."""

    def __init__(
        self,
        *,
        pool: asyncpg.Pool | None = None,
        anthropic_client: anthropic.AsyncAnthropic | None = None,
        anthropic_model: str | None = None,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        self._pool = pool
        self._anthropic_client = anthropic_client
        self._anthropic_model = anthropic_model
        self._rrf_k = rrf_k

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 10) -> RetrievalResult:
        tenant_id = _require_tenant_id(tenant_id)
        legs = await hybrid_search(query, tenant_id, top_k=top_k, pool=self._pool)
        ranked = fuse_hybrid_legs(legs, top_k=top_k, k=self._rrf_k)
        return RetrievalResult(query=query, tenant_id=tenant_id, ranked=ranked)

    async def answer(self, query: str, tenant_id: UUID, top_k: int = 10) -> SynthesizedAnswer:
        tenant_id = _require_tenant_id(tenant_id)
        retrieval = await self.retrieve(query, tenant_id, top_k=top_k)
        return await synthesize_answer(
            query,
            tenant_id,
            retrieval.ranked,
            client=self._anthropic_client,
            model=self._anthropic_model,
            pool=self._pool,
        )
