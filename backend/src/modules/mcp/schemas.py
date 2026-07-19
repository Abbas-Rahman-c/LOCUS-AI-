"""
MCPToolRequest / MCPToolResponse schemas -- the envelope every MCP tool
call in modules.mcp.tools goes through, and what gets logged (minus
`params`, which may carry free-text query strings) to public.mcp_tool_calls.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MCPToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(..., min_length=1)
    tenant_id: UUID
    requesting_client: str = Field(..., min_length=1, description="e.g. 'claude-desktop', 'claude-code'")
    params: dict[str, Any] = Field(default_factory=dict)


class MCPToolResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    result: dict[str, Any]
    result_decision_ids: list[UUID] = Field(default_factory=list)
    latency_ms: int
