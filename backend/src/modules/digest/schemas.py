"""
Digest schemas — strict Pydantic v2 contracts for the Team Pulse weekly digest.

DigestScope controls whether the digest is scoped to one person ("personal")
or the whole team ("team").

DigestItem is one decision entry in the digest — a thin projection of a
decision record, not a full SearchResponse, because the digest is a
*summary* of the week, not an answer to a question.

DigestResponse is the final API response shape returned by GET /digest.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DigestItem(BaseModel):
    """One decision surfaced in the weekly digest."""

    model_config = ConfigDict(extra="forbid")

    decision_statement: str
    rationale: str | None = None
    confidence: float
    created_at: str | None = None


class DigestMetadata(BaseModel):
    """Pipeline statistics for one digest generation call."""

    model_config = ConfigDict(extra="forbid")

    model: str
    latency_ms: float
    decision_count: int
    token_estimate: int
    personalized: bool = Field(
        default=True,
        description=(
            "For scope='personal': whether the caller's actor identity could "
            "be resolved (actors.auth_user_id) and used to ask a genuinely "
            "answerable 'decisions I was involved in' question. False means "
            "no such linkage exists yet for this account, so the digest fell "
            "back to the same broad team-wide question as scope='team' — "
            "this keeps summary and items consistent instead of Claude "
            "truthfully refusing an unanswerable first-person question. "
            "Always True for scope='team' (the question never depends on "
            "caller identity there)."
        ),
    )


class DigestResponse(BaseModel):
    """GET /digest response body."""

    model_config = ConfigDict(extra="forbid")

    scope: Literal["personal", "team"]
    period: str = Field(
        ...,
        description="ISO 8601 date range string, e.g. '2025-07-14/2025-07-21'",
    )
    summary: str = Field(..., description="Claude-generated prose summary of the week's decisions")
    items: list[DigestItem]
    metadata: DigestMetadata
