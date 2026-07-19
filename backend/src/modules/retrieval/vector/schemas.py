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
