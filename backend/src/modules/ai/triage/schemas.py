"""
TriageResult — Pydantic v2 contract for the Haiku triage stage output.

Stage 1 of the AI pipeline decides whether an event is worth the (more
expensive) extraction stage. The model itself speaks in uppercase decision
words; raw_events.triage_result is a lowercase DB enum ('kept', 'discarded',
'uncertain') — TriageResult.db_triage_result bridges the two so the mapping
lives in exactly one place.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TriageDecision(StrEnum):
    """Haiku's triage verdict on an event. Uppercase at the AI boundary."""

    KEEP = "KEEP"
    DISCARD = "DISCARD"
    UNCERTAIN = "UNCERTAIN"


class TriageReasonCode(StrEnum):
    """Why Haiku reached its TriageDecision — used for prompt evaluation and audit."""

    EXPLICIT_DECISION = "EXPLICIT_DECISION"
    ACTION_ASSIGNED = "ACTION_ASSIGNED"
    BLOCKER_IDENTIFIED = "BLOCKER_IDENTIFIED"
    CONFIRMED_CHANGE = "CONFIRMED_CHANGE"
    TENTATIVE_PROPOSAL = "TENTATIVE_PROPOSAL"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    SOCIAL_CHATTER = "SOCIAL_CHATTER"
    AUTOMATED_NOTIFICATION = "AUTOMATED_NOTIFICATION"
    UNRELATED_CONTENT = "UNRELATED_CONTENT"


_DB_TRIAGE_RESULT_BY_DECISION: dict[TriageDecision, str] = {
    TriageDecision.KEEP: "kept",
    TriageDecision.DISCARD: "discarded",
    TriageDecision.UNCERTAIN: "uncertain",
}


class TriageResult(BaseModel):
    """Validated output of the Haiku triage call for a single event."""

    model_config = ConfigDict(extra="forbid")

    decision: TriageDecision = Field(..., description="Haiku's KEEP / DISCARD / UNCERTAIN verdict.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Haiku's self-reported confidence in the decision, 0-1.")
    reason_code: TriageReasonCode = Field(..., description="Structured reason code explaining the decision.")

    @property
    def db_triage_result(self) -> str:
        """Lowercase value for raw_events.triage_result (e.g. KEEP -> 'kept')."""
        return _DB_TRIAGE_RESULT_BY_DECISION[self.decision]
