"""
Vector retrieval schemas — strict Pydantic v2 contracts for the tenant-scoped
similarity search engine.

RetrievalMatch mirrors exactly the columns
modules.retrieval.vector.repository.search_similar_decisions() selects from
public.decisions joined with public.decision_embeddings, inside a single
tenant's RLS-scoped transaction - nothing else (no raw_content, no capture
text, no reranking/citation fields).
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_TOP_K = 5
MAX_TOP_K = 50

# Candidate pool size fetched from the DB before permission filtering +
# cross-encoder reranking narrow it down to top_k ("smarter retrieval" -
# retrieve broad, then let the reranker pick the best ones, instead of
# asking the DB's cosine/FTS ranking alone to be precise at top_k=5).
DEFAULT_CANDIDATE_K = 20

# Must match common.config.voyage_config.REQUIRED_OUTPUT_DIMENSION and the
# live decision_embeddings.embedding column type (vector(1024)).
REQUIRED_EMBEDDING_DIMENSION = 1024


class RetrievalMatch(BaseModel):
    """One decision_embeddings/decisions row returned by a tenant-scoped similarity search."""

    model_config = ConfigDict(extra="forbid")

    decision_id: UUID
    decision_statement: str
    similarity_score: float
    confidence: float
    tenant_id: UUID
    permission_scope: list[str]
    rationale: str | None = None
    alternatives_considered: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    decision_type: str | None = None
    owner: str | None = None
    # Originating connector ("slack" | "gmail" | "notion"), joined from
    # raw_events via decisions.origin_raw_event_id. None only for a
    # decision whose origin_raw_event_id is null (schema allows this).
    source: str | None = None
    # Set only by modules.retrieval.reranking.rrf.fuse_rrf() in hybrid_rrf
    # mode; None for semantic_only/keyword_only matches, which are already
    # ordered by their own method's score and never carry a fused score.
    rrf_score: float | None = None
    # Set only by modules.retrieval.reranking.cross_encoder.rerank(); None
    # for any match that hasn't been through reranking yet.
    rerank_score: float | None = None
