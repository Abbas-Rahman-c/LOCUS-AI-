"""
Voyage embedding pipeline — strict Pydantic v2 contracts.

DecisionEmbeddingInput is what process_embedding_job() builds from a
fetched public.decisions row before calling embed_document() — never
raw_content, permission_scope, actor ids, or tenant/database metadata, just
the text that gets embedded. DecisionEmbeddingResult is the validated,
ready-to-persist output: embedding length and dimension are both pinned to
public.decision_embeddings.embedding's vector(1024) column
(migrations/010_decision_embeddings_voyage_ai.sql).
"""
from __future__ import annotations

import math
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REQUIRED_EMBEDDING_DIMENSION = 1024


class DecisionEmbeddingInput(BaseModel):
    """Input to the embed step for one decision."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    decision_id: UUID
    searchable_text: str = Field(..., min_length=1)


class DecisionEmbeddingResult(BaseModel):
    """One decision's embedding, ready to upsert into public.decision_embeddings."""

    model_config = ConfigDict(extra="forbid")

    decision_id: UUID
    tenant_id: UUID
    embedding: list[float]
    embedding_model: str = Field(..., min_length=1)
    dimension: int

    @field_validator("embedding")
    @classmethod
    def _validate_embedding_values(cls, v: list[float]) -> list[float]:
        if len(v) != REQUIRED_EMBEDDING_DIMENSION:
            raise ValueError(
                f"embedding must have exactly {REQUIRED_EMBEDDING_DIMENSION} values, got {len(v)}"
            )
        if not all(math.isfinite(x) for x in v):
            raise ValueError("embedding values must all be finite numbers")
        return v

    @model_validator(mode="after")
    def _dimension_matches_embedding_length(self) -> DecisionEmbeddingResult:
        if self.dimension != len(self.embedding):
            raise ValueError(
                f"dimension ({self.dimension}) must equal len(embedding) ({len(self.embedding)})"
            )
        return self
