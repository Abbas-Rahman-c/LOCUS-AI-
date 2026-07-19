"""
Shared retrieval schemas -- the contract every retrieval-stage module
(hybrid, rrf, resolver, synthesizer, pipeline, and the eval harness'
mock_pipeline) speaks, so they compose without any module needing to know
another's internals.

RetrievedDecision is deliberately DB-shaped (mirrors public.decisions +
public.decision_sources columns) rather than tied to any one retrieval leg,
so the same type comes back whether a decision was found by vector search,
full-text search, or (in the mock pipeline) an in-memory list.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetrievedDecision(BaseModel):
    """One candidate decision on its way through the retrieval pipeline."""

    model_config = ConfigDict(extra="forbid")

    decision_id: UUID
    tenant_id: UUID
    decision_statement: str
    rationale: str | None = None
    status: str = Field(..., description="proposed | decided | superseded")
    record_type: str = Field(default="decision", description="decision | action_item | blocker")
    source_permalink: str | None = None

    # Per-leg debug signal -- populated by whichever leg(s) surfaced this
    # decision. None means "this leg did not return this candidate."
    vector_rank: int | None = None
    vector_score: float | None = None  # cosine similarity, higher is better
    keyword_rank: int | None = None
    keyword_score: float | None = None  # ts_rank, higher is better


class RankedDecision(BaseModel):
    """A RetrievedDecision after RRF fusion, with a final blended rank/score."""

    model_config = ConfigDict(extra="forbid")

    decision: RetrievedDecision
    rrf_score: float
    rank: int = Field(..., ge=1)


class RetrievalResult(BaseModel):
    """What retrieve() returns: a tenant-scoped, ranked candidate list."""

    model_config = ConfigDict(extra="forbid")

    query: str
    tenant_id: UUID
    ranked: list[RankedDecision]

    @property
    def decision_ids(self) -> list[UUID]:
        return [r.decision.decision_id for r in self.ranked]


class Citation(BaseModel):
    """One decision cited by a synthesized answer."""

    model_config = ConfigDict(extra="forbid")

    decision_id: UUID
    permalink: str | None = None


class SynthesizedAnswer(BaseModel):
    """What answer() / synthesize() returns."""

    model_config = ConfigDict(extra="forbid")

    query: str
    tenant_id: UUID
    answer_text: str
    citations: list[Citation] = Field(default_factory=list)
    grounded_in: list[UUID] = Field(
        default_factory=list,
        description="decision_ids the model was actually shown when generating this answer "
        "(the full retrieved+fused set, a superset of citations) -- used by the groundedness judge.",
    )

    @property
    def cited_decision_ids(self) -> list[UUID]:
        return [c.decision_id for c in self.citations]
