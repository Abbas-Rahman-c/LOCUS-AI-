"""
MCP server — HTTP JSON-RPC 2.0 endpoint.

The Model Context Protocol uses JSON-RPC 2.0 over HTTP (or stdio).
Since no Python MCP SDK is installed, this implements the wire protocol
directly as a FastAPI router mounted at /mcp.

Auth: EXACTLY the same tenant-scoped JWT used by the UI path.
MCP clients must supply:  Authorization: Bearer <tenant_jwt>

There is NO separate auth mechanism for MCP — it is not exempted from
tenant scoping under any circumstance.

Supported tools:
  - search_decisions   { query: str, limit?: int }
  - get_decision_context  { decision_id: str }

Wire protocol reference:
  https://modelcontextprotocol.io/docs/concepts/transports
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.dependencies import TenantContext, get_current_tenant
from database.pool import get_db_pool
from modules.mcp.tools.context import get_decision_context_tool
from modules.mcp.tools.search import search_decisions_tool

log = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])

# ── Tool registry ──────────────────────────────────────────────────────────────

_TOOL_SCHEMAS = [
    {
        "name": "search_decisions",
        "description": (
            "Search for decisions in the authenticated tenant's workspace "
            "using a free-text query."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text search query"},
                "limit": {"type": "integer", "description": "Max results (1-50)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_decision_context",
        "description": (
            "Fetch a single decision and its source links for use in AI context."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "decision_id": {"type": "string", "format": "uuid"},
            },
            "required": ["decision_id"],
        },
    },
]


def _jsonrpc_error(id_: Any, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": id_,
        "error": {"code": code, "message": message},
    }


def _jsonrpc_ok(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get(
    "/tools/list",
    summary="List available MCP tools",
)
async def list_tools(ctx: TenantContext = Depends(get_current_tenant)) -> dict:
    """Returns the tool manifest — auth required."""
    return {"tools": _TOOL_SCHEMAS}


@router.post(
    "",
    summary="MCP JSON-RPC 2.0 dispatch",
)
async def mcp_dispatch(
    request: Request,
    ctx: TenantContext = Depends(get_current_tenant),
) -> JSONResponse:
    """
    Dispatch a JSON-RPC 2.0 MCP tool call.

    Auth: same Bearer tenant JWT as every other endpoint.
    The tenant_id from the JWT is propagated to every tool — MCP clients cannot
    override or elevate their tenant scope.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(_jsonrpc_error(None, -32700, "Parse error"), status_code=400)

    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    # Handle MCP initialize handshake
    if method == "initialize":
        return JSONResponse(_jsonrpc_ok(rpc_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "locus-ai", "version": "0.1.0"},
        }))

    if method == "tools/list":
        return JSONResponse(_jsonrpc_ok(rpc_id, {"tools": _TOOL_SCHEMAS}))

    if method != "tools/call":
        return JSONResponse(
            _jsonrpc_error(rpc_id, -32601, f"Method not found: {method!r}"),
            status_code=200,  # JSON-RPC errors always return HTTP 200
        )

    tool_name = params.get("name", "")
    tool_args: dict = params.get("arguments", {})
    pool = get_db_pool()

    t0 = time.monotonic()
    try:
        if tool_name == "search_decisions":
            result = await search_decisions_tool(tool_args, ctx, pool)
        elif tool_name == "get_decision_context":
            result = await get_decision_context_tool(tool_args, ctx, pool)
        else:
            return JSONResponse(
                _jsonrpc_ok(rpc_id, {
                    "content": [{"type": "text", "text": f"Unknown tool: {tool_name!r}"}],
                    "isError": True,
                })
            )
    except PermissionError as exc:
        # Layer 2 (assert_tenant_scope) fired — log and return generic error
        log.warning("Tenant scope violation in MCP tool %s: %s", tool_name, exc)
        return JSONResponse(
            _jsonrpc_ok(rpc_id, {
                "content": [{"type": "text", "text": "Access denied"}],
                "isError": True,
            })
        )
    except Exception as exc:
        log.exception("MCP tool %s failed: %s", tool_name, exc)
        return JSONResponse(
            _jsonrpc_ok(rpc_id, {
                "content": [{"type": "text", "text": "Internal error"}],
                "isError": True,
            })
        )

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "MCP tool=%s tenant=%s latency=%dms results=%d",
        tool_name,
        ctx.tenant_id,
        elapsed_ms,
        result.get("total", 1),
    )

    return JSONResponse(
        _jsonrpc_ok(rpc_id, {
            "content": [{"type": "text", "text": str(result)}],
            "structuredContent": result,
            "isError": False,
        })
    )
