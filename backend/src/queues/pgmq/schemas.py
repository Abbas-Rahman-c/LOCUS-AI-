"""
pgmq message schemas - strict Pydantic v2 contracts for queue payloads.

Each schema carries only the keys a worker needs to re-fetch its own data
from PostgreSQL - never the data itself. extra="forbid" on every model so a
stale producer can't silently widen what crosses the queue.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EmbeddingJob(BaseModel):
    """Queue payload for QueueName.EMBEDDING.

    Carries only tenant_id and decision_id. The embedding worker fetches the
    persisted decision (statement, rationale, etc.) from PostgreSQL itself -
    no text content, model output, or vector data ever crosses the queue.
    Re-processing the same (tenant_id, decision_id) job is idempotent: see
    modules.ai.embeddings.service.process_embedding_job()'s upsert.
    """

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    decision_id: UUID
