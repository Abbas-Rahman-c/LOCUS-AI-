"""
AIProcessingResult — Pydantic v2 contract for one process_ai_event() run.

Wraps the two-stage AI pipeline's output: triage always runs, extraction
runs unless triage discarded the event. This model carries only stage
outputs — no tenant_id, permission_scope, database ids, timestamps, model
name, or prompt version. Those belong to the caller/persistence layer, which
this module never touches.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from modules.ai.extraction.schemas import ExtractionResult
from modules.ai.triage.schemas import TriageDecision, TriageResult


class AIProcessingResult(BaseModel):
    """Result of running the full triage -> extraction pipeline on one event.

    extraction is None if and only if triage.decision is DISCARD — KEEP and
    UNCERTAIN both require an extraction attempt, so a mismatch here is a
    pipeline bug, not a valid result.
    """

    model_config = ConfigDict(extra="forbid")

    triage: TriageResult
    extraction: ExtractionResult | None = None

    @model_validator(mode="after")
    def _extraction_matches_triage_decision(self) -> AIProcessingResult:
        if self.triage.decision == TriageDecision.DISCARD:
            if self.extraction is not None:
                raise ValueError("extraction must be None when triage.decision is DISCARD")
        elif self.extraction is None:
            raise ValueError(
                f"extraction is required when triage.decision is {self.triage.decision.value}"
            )
        return self


class IngestionProcessingResult(BaseModel):
    """Result of running process_and_persist_event() on one event.

    decision_id, persisted, and embedding_enqueued always agree with
    triage.decision: DISCARD means no extraction, no persistence attempt, no
    decision_id, and no embedding enqueue. KEEP and UNCERTAIN both persist
    the extracted record, come back with the created decision's id, and have
    an embedding job enqueued - process_and_persist_event() raises instead of
    returning a result if enqueue fails, so embedding_enqueued is never False
    while persisted is True.
    """

    model_config = ConfigDict(extra="forbid")

    triage: TriageResult
    extraction: ExtractionResult | None = None
    decision_id: UUID | None = None
    persisted: bool
    embedding_enqueued: bool

    @model_validator(mode="after")
    def _fields_agree_with_triage_decision(self) -> IngestionProcessingResult:
        if self.triage.decision == TriageDecision.DISCARD:
            if self.extraction is not None:
                raise ValueError("extraction must be None when triage.decision is DISCARD")
            if self.decision_id is not None:
                raise ValueError("decision_id must be None when triage.decision is DISCARD")
            if self.persisted is not False:
                raise ValueError("persisted must be False when triage.decision is DISCARD")
            if self.embedding_enqueued is not False:
                raise ValueError("embedding_enqueued must be False when triage.decision is DISCARD")
        else:
            if self.extraction is None:
                raise ValueError(
                    f"extraction is required when triage.decision is {self.triage.decision.value}"
                )
            if self.decision_id is None:
                raise ValueError(
                    f"decision_id is required when triage.decision is {self.triage.decision.value}"
                )
            if self.persisted is not True:
                raise ValueError(
                    f"persisted must be True when triage.decision is {self.triage.decision.value}"
                )
            if self.embedding_enqueued is not True:
                raise ValueError(
                    f"embedding_enqueued must be True when triage.decision is {self.triage.decision.value}"
                )
        return self
