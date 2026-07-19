"""
KnownCandidateRAGPipeline -- a RAGPipeline Protocol implementation for
environments that can reach Anthropic but cannot reach Postgres or Voyage
(e.g. a sandboxed CI/build environment behind an egress allowlist that
permits api.anthropic.com but not a Supabase pooler host or
api.voyageai.com).

This is NOT a substitute for MockRAGPipeline and NOT a substitute for the
real modules.retrieval.pipeline.RAGPipeline. It sits between them:

  - retrieve() is NOT real retrieval. It returns a fixed, hand-picked
    candidate pool (typically a ScenarioPack's own decisions) with no
    ranking signal of its own -- Recall@K/MRR/Hit-Rate/latency computed
    against its output do not measure retrieval quality and should be
    treated as not meaningful, not as a real number.
  - answer() calls the REAL modules.retrieval.synthesis.synthesizer.
    synthesize_answer() -- a genuine Sonnet/Haiku API call, forced tool-use,
    real citation-label mapping -- over that candidate pool. Groundedness
    and correctness scores from modules.retrieval.evaluation.llm_judge
    (also a real API call) on top of that ARE real: they measure "given
    these candidates, does the model write a grounded, correct, well-cited
    answer," which is exactly what synthesizer.py needs to be tested for
    doesn't depend on Postgres or Voyage.

Use this when you want a real, credit-consuming Anthropic exchange without
a live database -- e.g. to bound API usage to a small hand-picked example
set. For a real Recall@K/MRR number, you need
modules.retrieval.pipeline.RAGPipeline against an actual Postgres+pgvector
instance with Voyage-embedded decisions (see docker-compose.yml).
"""
from __future__ import annotations

from uuid import UUID

from modules.retrieval.evaluation.golden_dataset import ScenarioDecision
from modules.retrieval.schemas import Citation, RankedDecision, RetrievalResult, RetrievedDecision, SynthesizedAnswer
from modules.retrieval.synthesis.synthesizer import synthesize_answer


class KnownCandidateRAGPipeline:
    """Fixed candidate pool (e.g. one ScenarioPack's decisions), real
    synthesis + judging. See module docstring for what is and isn't real
    about this."""

    def __init__(self, decisions: list[ScenarioDecision]) -> None:
        self._decisions = decisions

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 10) -> RetrievalResult:
        candidates = [d for d in self._decisions if d.tenant_id == tenant_id][:top_k]
        ranked = [
            RankedDecision(
                decision=RetrievedDecision(
                    decision_id=d.decision_id,
                    tenant_id=d.tenant_id,
                    decision_statement=d.decision_statement,
                    rationale=d.rationale,
                    status=d.status,
                    record_type=d.record_type,
                    source_permalink=d.source_permalink,
                ),
                rrf_score=1.0 / (i + 1),  # arbitrary, fixed-pool ordering -- not a real ranking signal
                rank=i + 1,
            )
            for i, d in enumerate(candidates)
        ]
        return RetrievalResult(query=query, tenant_id=tenant_id, ranked=ranked)

    async def answer(self, query: str, tenant_id: UUID, top_k: int = 10) -> SynthesizedAnswer:
        retrieval = await self.retrieve(query, tenant_id, top_k=top_k)
        # Real Anthropic call -- forced tool-use synthesis over the fixed pool.
        # resolve_permalinks=False skips the DB round-trip resolver.py would
        # otherwise make (no live DB here) -- permalinks are filled back in
        # below from the already-known ScenarioDecision data instead.
        result = await synthesize_answer(query, tenant_id, retrieval.ranked, resolve_permalinks=False)

        permalink_by_id = {d.decision_id: d.source_permalink for d in self._decisions}
        result.citations = [
            Citation(decision_id=c.decision_id, permalink=permalink_by_id.get(c.decision_id))
            for c in result.citations
        ]
        return result
