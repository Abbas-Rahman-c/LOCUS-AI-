"""
AIProcessingResult — Pydantic v2 contract for one process_ai_event() run.

Wraps the two-stage AI pipeline's output: triage always runs, extraction
runs unless triage discarded the event. This model carries only stage
outputs — no tenant_id, permission_scope, database ids, timestamps, model
name, or prompt version. Those belong to the caller/persistence layer, which
this module never touches.
"""
from __future__ import annotations

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
