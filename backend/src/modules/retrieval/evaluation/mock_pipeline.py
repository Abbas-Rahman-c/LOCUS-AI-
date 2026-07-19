"""
MockRAGPipeline -- a zero-I/O stand-in for modules.retrieval.pipeline.RAGPipeline,
used by scripts/run_rag_eval.py before hybrid.py/rrf.py/synthesizer.py/resolver.py
existed (and still useful afterward as a fast, deterministic smoke test that
doesn't need a live DB or ANTHROPIC_API_KEY/VOYAGE_API_KEY).

Retrieval here is a crude bag-of-words Jaccard overlap between the question
and each candidate decision's statement+rationale -- no embeddings, no
Postgres full-text ranking, no RRF fusion of two independently-imperfect
legs. It tends to score *better* than the real pipeline on single_hop and
worse on paraphrase (no shared vocabulary to overlap on) and on suppressing
similar-topic distractors (no semantic distinction between "same domain,
different decision" and "the actual answer") -- which is exactly why this
mock's Recall@K/MRR are highs that the real RAGPipeline is expected to miss,
and why its negative_hit_rate is not a reliable estimate of the real
pipeline's false-positive rate. Synthesis here is equally crude: the
top-ranked candidate's own text, returned verbatim as the "answer" and
cited automatically. It is not calling any LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from modules.retrieval.schemas import (
    Citation,
    RankedDecision,
    RetrievalResult,
    RetrievedDecision,
    SynthesizedAnswer,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "we", "our", "us", "did", "do", "does", "what", "which", "who", "when",
    "where", "why", "how", "about", "on", "in", "at", "to", "for", "of",
    "and", "or", "with", "that", "this", "it", "have", "has", "had", "not",
}


def _tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


@dataclass(frozen=True)
class MockDecisionRecord:
    """The mock decision store's unit -- deliberately narrower than
    modules.retrieval.schemas.RetrievedDecision (no status/record_type),
    matching exactly what scripts/run_rag_eval.py's
    _decision_store_from_scenario_packs() constructs from ScenarioDecision."""

    decision_id: UUID
    tenant_id: UUID
    decision_statement: str
    rationale: str | None
    source_permalink: str | None


class MockRAGPipeline:
    """In-memory RAGPipeline Protocol implementation over a fixed list of
    MockDecisionRecord. No network, no DB, no Anthropic/Voyage calls --
    safe to run in any environment, including CI with no credentials."""

    def __init__(self, decisions: list[MockDecisionRecord]) -> None:
        self._decisions = decisions

    def _tenant_candidates(self, tenant_id: UUID) -> list[MockDecisionRecord]:
        return [d for d in self._decisions if d.tenant_id == tenant_id]

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 10) -> RetrievalResult:
        query_tokens = _tokenize(query)
        scored: list[tuple[float, MockDecisionRecord]] = []
        for record in self._tenant_candidates(tenant_id):
            doc_tokens = _tokenize(f"{record.decision_statement} {record.rationale or ''}")
            score = _jaccard(query_tokens, doc_tokens)
            if score > 0:
                scored.append((score, record))

        scored.sort(key=lambda item: (-item[0], str(item[1].decision_id)))
        top = scored[:top_k]

        ranked = [
            RankedDecision(
                decision=RetrievedDecision(
                    decision_id=record.decision_id,
                    tenant_id=record.tenant_id,
                    decision_statement=record.decision_statement,
                    rationale=record.rationale,
                    status="decided",
                    record_type="decision",
                    source_permalink=record.source_permalink,
                ),
                rrf_score=score,
                rank=i + 1,
            )
            for i, (score, record) in enumerate(top)
        ]
        return RetrievalResult(query=query, tenant_id=tenant_id, ranked=ranked)

    async def answer(self, query: str, tenant_id: UUID, top_k: int = 10) -> SynthesizedAnswer:
        retrieval = await self.retrieve(query, tenant_id, top_k=top_k)
        if not retrieval.ranked:
            return SynthesizedAnswer(
                query=query,
                tenant_id=tenant_id,
                answer_text="There's no recorded decision that answers this question.",
                citations=[],
                grounded_in=[],
            )

        top_decision = retrieval.ranked[0].decision
        answer_text = top_decision.decision_statement
        if top_decision.rationale:
            answer_text = f"{answer_text} {top_decision.rationale}"

        return SynthesizedAnswer(
            query=query,
            tenant_id=tenant_id,
            answer_text=answer_text,
            citations=[
                Citation(decision_id=top_decision.decision_id, permalink=top_decision.source_permalink)
            ],
            grounded_in=[r.decision.decision_id for r in retrieval.ranked],
        )
