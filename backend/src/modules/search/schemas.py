"""
Search schemas — strict Pydantic v2 contracts for the production POST
/search endpoint: authenticated tenant-scoped vector retrieval ->
permission filtering -> context builder -> Claude answer, combined into
one response.

tenant_id is deliberately NOT a field here - it is derived exclusively
from the authenticated TenantContext (app.dependencies.get_current_tenant)
at the router layer, never from the request body.

permission_scopes is deliberately NOT a field here either, and never was
safe to keep as one: it is authorization data, not a search input, and a
client asking for a scope is not evidence it is entitled to it. The
router resolves the caller's authorized scopes server-side via
modules.permissions.scope_resolver.resolve_permission_scopes(ctx), using
only the authenticated TenantContext (user_id, tenant_id, role) - never
anything from this request body. See that module's docstring for the
repository evidence behind what scopes an authenticated caller is
actually granted.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.retrieval.vector.schemas import DEFAULT_TOP_K, MAX_TOP_K


class SearchRequest(BaseModel):
    """POST /search request body: search inputs only, no authorization data."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)


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
    # Additive fields (production RAG upgrade) - all optional-with-default
    # so any existing consumer that only reads the fields above is
    # unaffected.
    question_type: str = "other"
    is_multi_document: bool = False
    reranked: bool = False


class SearchResponse(BaseModel):
    """POST /search response body."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[SourceCitation]
    metadata: SearchMetadata
    # Additive fields (production RAG upgrade): reasoning is Claude's own
    # brief grounding explanation (see modules.answering.prompt_builder),
    # confidence is Claude's self-reported confidence in the answer.
    # Existing consumers reading only answer/citations/metadata are
    # unaffected.
    reasoning: str = ""
    confidence: float = 0.0
