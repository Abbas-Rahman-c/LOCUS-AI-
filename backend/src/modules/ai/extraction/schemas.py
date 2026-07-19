"""
ExtractionResult — Pydantic v2 contract for the extraction stage output.

Field names and enum values are aligned to the real public.decisions table
(backend/src/database/sql/schema.sql), not older design-document vocabulary
(e.g. 'decision_statement'/'alternatives_considered', not
'statement'/'alternatives').

This model only carries what the model itself can produce. tenant_id, scope,
scope_actor_id, permission_scope, origin_raw_event_id, and the row's
id/timestamps are assigned later by the backend persistence layer — they are
deliberately absent here so the AI boundary can't forge tenant-scoped or
database-owned fields.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecordType(StrEnum):
    """Mirrors public.decisions.record_type check constraint."""

    DECISION = "decision"
    ACTION_ITEM = "action_item"
    BLOCKER = "blocker"


class DecisionStatus(StrEnum):
    """Mirrors public.decisions.status check constraint."""

    PROPOSED = "proposed"
    DECIDED = "decided"
    SUPERSEDED = "superseded"


class ActorRole(StrEnum):
    """Role an actor plays with respect to the extracted record.

    Mirrors public.decision_actors.role check constraint.
    """

    DECIDED_BY = "decided_by"
    MENTIONED = "mentioned"


class ActorReference(BaseModel):
    """A single actor mentioned in or responsible for the extracted record."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_actor_id: str = Field(..., min_length=1, description="Provider-native id of the referenced actor.")
    role: ActorRole = Field(..., description="How this actor relates to the extracted record.")


class ExtractionResult(BaseModel):
    """Validated output of the extraction call for a single KEEP/UNCERTAIN event."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    record_type: RecordType = Field(..., description="decision | action_item | blocker — matches decisions.record_type.")
    status: DecisionStatus = Field(..., description="proposed | decided | superseded — matches decisions.status.")
    decision_statement: str = Field(..., min_length=1, description="The core statement being recorded, maps to decisions.decision_statement.")
    rationale: str | None = Field(default=None, description="Why the decision/action/blocker was reached, if stated.")
    alternatives_considered: list[str] = Field(
        default_factory=list,
        description="Other options that were considered, maps to decisions.alternatives_considered.",
    )
    actors: list[ActorReference] = Field(
        default_factory=list,
        description="Actors referenced by the record, e.g. who decided or who is mentioned.",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="The model's self-reported confidence in the extraction, 0-1.")

    @field_validator("alternatives_considered")
    @classmethod
    def _clean_alternatives(cls, v: list[str]) -> list[str]:
        """Drop blanks and deduplicate while preserving first-seen order."""
        seen: set[str] = set()
        cleaned: list[str] = []
        for alt in v:
            if not alt or alt in seen:
                continue
            seen.add(alt)
            cleaned.append(alt)
        return cleaned

    @model_validator(mode="after")
    def _at_most_one_decided_by(self) -> ExtractionResult:
        decided_by_count = sum(1 for actor in self.actors if actor.role == ActorRole.DECIDED_BY)
        if decided_by_count > 1:
            raise ValueError("at most one actor may have role 'decided_by'")
        return self
