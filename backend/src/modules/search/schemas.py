"""
Search schemas — strict Pydantic v2 contracts for the production POST
/search endpoint: authenticated tenant-scoped vector retrieval ->
permission filtering -> context builder -> Claude answer, combined into
one response.

tenant_id is deliberately NOT a field here - it is derived exclusively
from the authenticated TenantContext (app.dependencies.get_current_tenant)
at the router layer, never from the request body.

permission_scopes IS a request field: unlike tenant_id (the hard RLS trust
boundary), it is not yet backed by any per-user scope source in this
codebase (memberships only carries tenant_id + role) - see the search
service module docstring for the open question this leaves for the
backend team. Defaults to empty, meaning "no scopes requested" rather
than "all scopes" - callers must say what they want considered.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.retrieval.vector.schemas import DEFAULT_TOP_K, MAX_TOP_K


class SearchRequest(BaseModel):
    """POST /search request body."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)
    permission_scopes: list[str] = Field(default_factory=list)


class SourceCitation(BaseModel):
    """One decision Claude's answer actually cited, resolved back to its source."""

    model_config = ConfigDict(extra="forbid")

    decision_number: int
    decision_id: UUID
    decision_statement: str
    confidence: float


class SearchMetadata(BaseModel):
    """Pipeline statistics for one /search call."""

    model_config = ConfigDict(extra="forbid")

    model: str
    latency_ms: float
    retrieved_count: int
    authorized_count: int
    decision_count: int
    token_estimate: int


class SearchResponse(BaseModel):
    """POST /search response body."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[SourceCitation]
    metadata: SearchMetadata
