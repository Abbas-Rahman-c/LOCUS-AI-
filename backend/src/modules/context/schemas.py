"""
Context schemas — strict Pydantic v2 contracts for turning authorized
decisions into a single formatted context string.

AuthorizedDecisionInput accepts rationale/alternatives/created_at/
decision_type/owner as optional: whatever the caller has is used
verbatim, and whatever is missing is rendered as an explicit placeholder
(or omitted entirely, for decision_type/owner) by formatter.py - never
fabricated.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuthorizedDecisionInput(BaseModel):
    """One authorized decision, ready to be rendered into context text."""

    model_config = ConfigDict(extra="forbid")

    decision_statement: str = Field(..., min_length=1)
    rationale: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    confidence: float
    created_at: str | None = None
    decision_type: str | None = None
    owner: str | None = None
    source: str | None = None
    # No impact/severity column exists in public.decisions today - this
    # field exists so the formatter can render it the moment a real value
    # is ever available, without inventing one now. Always None currently.
    impact: str | None = None


class ContextResult(BaseModel):
    """build_context()'s return value."""

    model_config = ConfigDict(extra="forbid")

    context: str
    decision_count: int
    token_estimate: int
