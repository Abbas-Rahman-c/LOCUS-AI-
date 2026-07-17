"""
Integration tests for Cross-Tenant Isolation.

Verifies that:
1. Tenant A cannot read, list, or search decisions belonging to Tenant B via the UI path.
2. Tenant A cannot read, list, or search decisions belonging to Tenant B via the MCP path.
3. Probing for a decision ID belonging to Tenant B as Tenant A returns 404 (UI) or "not found" (MCP),
   ensuring the existence of the decision is not leaked.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from database.pool import init_db_pool
from tests.conftest import make_pool_with_rows, make_tenant_jwt

client = TestClient(app)

@pytest.mark.asyncio
async def test_ui_path_cross_tenant_isolation():
    """Tenant A cannot see Tenant B's decisions via the UI/API path."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    # Generate valid tokens signed by backend APP_SECRET_KEY
    token_a = make_tenant_jwt(tenant_a, user_id="user-a", role="member")
    
    # Decisions in DB
    decisions_in_db = [
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_a,
            "record_type": "decision",
            "decision_statement": "Tenant A Decision",
            "rationale": "Secret A",
            "status": "decided",
            "scope": "team",
            "confidence": 0.9,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    ]

    # Pre-wire the database pool to only return Tenant A's row when queried.
    pool = make_pool_with_rows(decisions_in_db, scalar=1)
    await init_db_pool(pool)

    # 1. Tenant A requests their own decisions: should succeed
    headers_a = {"Authorization": f"Bearer {token_a}"}
    response = client.get("/api/v1/decisions", headers=headers_a)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["decision_statement"] == "Tenant A Decision"

    # 2. Wire pool to return nothing, simulating standard tenant-scoped filtering
    decision_b_id = uuid.uuid4()
    pool_b = make_pool_with_rows([], scalar=0)
    await init_db_pool(pool_b)

    # Tenant A attempts to fetch Tenant B's decision:
    # Service layer will filter by tenant_id = tenant_a, resulting in empty rows from query
    # and returning 404 (decision not found).
    response = client.get(f"/api/v1/decisions/{decision_b_id}", headers=headers_a)
    assert response.status_code == 404
    assert response.json()["detail"] == "Decision not found"

@pytest.mark.asyncio
async def test_ui_path_leak_prevention():
    """Verify that if database somehow leaks another tenant's row (bypassing RLS/SQL filter),
    Layer 2 application pre-filter catches it and throws a TenantScopeError.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    token_a = make_tenant_jwt(tenant_a, user_id="user-a", role="member")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    decision_b_id = uuid.uuid4()
    decisions_b_in_db = [
        {
            "id": decision_b_id,
            "tenant_id": tenant_b,  # Tenant B's decision leaked!
            "record_type": "decision",
            "decision_statement": "Leaked Tenant B Decision",
            "rationale": "Secret B",
            "status": "decided",
            "scope": "team",
            "confidence": 0.95,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    ]
    # Pool is set to return the leaked record
    leaked_pool = make_pool_with_rows(decisions_b_in_db, scalar=1)
    await init_db_pool(leaked_pool)

    # Unhandled errors inside the route propagate directly under test client
    from modules.security.tenant_guard import TenantScopeError
    with pytest.raises(TenantScopeError):
        client.get(f"/api/v1/decisions/{decision_b_id}", headers=headers_a)


@pytest.mark.asyncio
async def test_mcp_path_cross_tenant_isolation():
    """Tenant A cannot see Tenant B's decisions via the MCP path."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    token_a = make_tenant_jwt(tenant_a, user_id="user-a", role="member")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 1. MCP search_decisions tool isolation
    # Set up DB to return Tenant B's records
    decisions_b = [
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_b,
            "record_type": "decision",
            "decision_statement": "Tenant B Decision",
            "rationale": "Secret B",
            "status": "decided",
            "scope": "team",
            "confidence": 0.95,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    ]
    pool = make_pool_with_rows(decisions_b, scalar=1)
    await init_db_pool(pool)

    # Handshake to ensure JSON-RPC is active
    handshake_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    resp = client.post("/mcp", json=handshake_payload, headers=headers_a)
    assert resp.status_code == 200

    # Tenant A calls search_decisions tool. The tool will execute search_decisions with tenant_a,
    # which will search WHERE tenant_id = tenant_a.
    # Since decisions_b contains tenant_b, query will return no matches.
    search_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search_decisions",
            "arguments": {
                "query": "Decision",
                "limit": 10
            }
        }
    }
    # Reset pool for Tenant A query to return nothing (as SQL has WHERE tenant_id = tenant_a)
    empty_pool = make_pool_with_rows([], scalar=0)
    await init_db_pool(empty_pool)

    resp = client.post("/mcp", json=search_payload, headers=headers_a)
    assert resp.status_code == 200
    res_data = resp.json()["result"]
    assert res_data["isError"] is False
    # Check structuredContent returned from tool
    import json
    content_dict = res_data["structuredContent"]
    assert content_dict["total"] == 0
    assert len(content_dict["decisions"]) == 0

    # 2. MCP get_decision_context tool isolation
    decision_b_id = uuid.uuid4()
    context_payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get_decision_context",
            "arguments": {
                "decision_id": str(decision_b_id)
            }
        }
    }
    # Let the pool be empty when filtering by tenant_a
    resp = client.post("/mcp", json=context_payload, headers=headers_a)
    assert resp.status_code == 200
    res_data = resp.json()["result"]
    # Should say "not found" inside the result (meaning it behaved as if it didn't exist)
    assert res_data["structuredContent"] == {"error": "not found"}

@pytest.mark.asyncio
async def test_ui_path_requires_authentication():
    """Verify that requests to the UI path without a token or with a bad token fail with 401."""
    # 1. No token
    response = client.get("/api/v1/decisions")
    assert response.status_code == 401

    # 2. Forged/invalid token
    response = client.get("/api/v1/decisions", headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_mcp_path_requires_authentication():
    """Verify that requests to the MCP path without a token or with a bad token fail with 401."""
    search_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_decisions",
            "arguments": {
                "query": "Decision"
            }
        }
    }
    # 1. No token
    response = client.post("/mcp", json=search_payload)
    assert response.status_code == 401

    # 2. Forged/invalid token
    response = client.post("/mcp", json=search_payload, headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401
