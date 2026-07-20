"""
Unit tests for the Retrieval + Synthesis QA Pipeline.
"""
from __future__ import annotations

import json
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import TenantContext
from database.pool import init_db_pool
from modules.retrieval import service
from modules.retrieval.router import router as retrieval_router
from modules.security.encryption import encrypt_raw_content
from modules.security.tenant_guard import TenantScopeError


class _FakeTransaction:
    """Minimal async-context-manager double for asyncpg's conn.transaction()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


# ── Router Test Setup ──────────────────────────────────────────────────────────

app = FastAPI()
app.include_router(retrieval_router)
client = TestClient(app)


# ── Service / Retrieval Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_decisions_basic(monkeypatch):
    """Test retrieve_decisions constructs SQL correctly and returns mapped fields."""
    tenant_id = uuid.uuid4()
    decision_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_dec_row = {
        "id": decision_id,
        "tenant_id": tenant_id,
        "decision_statement": "We chose PostgreSQL.",
        "rationale": "Better support for JSON and pgvector.",
        "alternatives_considered": ["MySQL", "MongoDB"],
        "status": "decided",
        "confidence": 0.95,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "relevance_score": 0.88,
    }

    mock_actor_row = {
        "tenant_id": tenant_id,
        "decision_id": decision_id,
        "actor_id": actor_id,
        "role": "decided_by",
    }

    mock_source_row = {
        "tenant_id": tenant_id,
        "decision_id": decision_id,
        "permalink": "https://slack.com/archives/123",
    }

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="SET")
    mock_conn.transaction = MagicMock(return_value=_FakeTransaction())
    
    # We mock connection fetch behavior based on query contents
    async def mock_fetch(query, *args):
        if "decision_actors" in query:
            return [mock_actor_row]
        elif "decision_sources" in query:
            return [mock_source_row]
        else:
            return [mock_dec_row]

    mock_conn.fetch = mock_fetch
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    res = await service.retrieve_decisions(
        query="PostgreSQL",
        tenant_id=tenant_id,
        filters={"status": "decided", "confidence_min": 0.8},
        limit=10,
        offset=0,
        pool=mock_pool,
    )

    assert len(res) == 1
    dec = res[0]
    assert dec["id"] == str(decision_id)
    assert dec["decision_statement"] == "We chose PostgreSQL."
    assert dec["rationale"] == "Better support for JSON and pgvector."
    assert dec["alternatives_considered"] == ["MySQL", "MongoDB"]
    assert dec["status"] == "decided"
    assert dec["confidence"] == 0.95
    assert dec["relevance_score"] == 0.88
    # Plural source_links and actors shape verification
    assert dec["source_links"] == ["https://slack.com/archives/123"]
    assert dec["actors"] == [{"id": str(actor_id), "role": "decided_by"}]


@pytest.mark.asyncio
async def test_retrieve_decisions_tenant_guard_violation():
    """Layer 2: retrieve_decisions raises TenantScopeError if DB returns row for another tenant."""
    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    
    mock_dec_row = {
        "id": uuid.uuid4(),
        "tenant_id": other_tenant_id, # mismatch!
        "decision_statement": "Bad Row.",
        "rationale": "Should be filtered.",
        "alternatives_considered": [],
        "status": "decided",
        "confidence": 1.0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "relevance_score": 1.0,
    }

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="SET")
    mock_conn.transaction = MagicMock(return_value=_FakeTransaction())
    mock_conn.fetch = AsyncMock(return_value=[mock_dec_row])
    
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with pytest.raises(TenantScopeError):
        await service.retrieve_decisions(
            query="test",
            tenant_id=tenant_id,
            pool=mock_pool,
        )


@pytest.mark.asyncio
async def test_get_decision_context_reconstructs_thread():
    """Test get_decision_context retrieves decisions and decrypts raw events to build thread context."""
    tenant_id = uuid.uuid4()
    decision_id = uuid.uuid4()
    event_id = uuid.uuid4()
    
    mock_dec_row = {
        "id": decision_id,
        "tenant_id": tenant_id,
        "decision_statement": "Statement.",
        "rationale": "Rationale.",
        "alternatives_considered": [],
        "status": "proposed",
        "confidence": 1.0,
        "origin_raw_event_id": event_id,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    # Encrypted event content matching EventEnvelope schema
    envelope = {
        "tenant_id": str(tenant_id),
        "source": "slack",
        "source_id": "msg_123",
        "actor": "user_abc",
        "thread_ref": "thread_abc",
        "raw_content": {
            "text": "Let's migrate to SQLite for local development."
        }
    }
    encrypted_bytes = encrypt_raw_content(json.dumps(envelope).encode("utf-8"))

    mock_event_row = {
        "tenant_id": tenant_id,
        "id": event_id,
        "source": "slack",
        "actor": "user_abc",
        "received_at": datetime.now(timezone.utc),
        "raw_content": encrypted_bytes,
    }

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="SET")
    mock_conn.transaction = MagicMock(return_value=_FakeTransaction())

    # Mock connection queries
    async def mock_fetchrow(query, *args):
        if "decisions" in query:
            return mock_dec_row
        return None

    async def mock_fetch(query, *args):
        if "decision_actors" in query:
            return []
        elif "decision_sources" in query:
            return []
        elif "DISTINCT thread_ref" in query:
            return [{"thread_ref": "thread_abc"}]
        elif "raw_events" in query:
            return [mock_event_row]
        return []

    mock_conn.fetchrow = mock_fetchrow
    mock_conn.fetch = mock_fetch

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    res = await service.get_decision_context(
        decision_id=decision_id,
        tenant_id=tenant_id,
        pool=mock_pool,
    )

    assert res is not None
    assert "SQLite" in res["thread_context"]
    assert "[slack]" in res["thread_context"] or "(slack)" in res["thread_context"]
    assert "user_abc" in res["thread_context"]


# ── Synthesis Pipeline Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_synthesis_model_lockdown(monkeypatch):
    """Test that synthesis fails if ANTHROPIC_SYNTHESIS_MODEL points to an unapproved model."""
    monkeypatch.setenv("ANTHROPIC_SYNTHESIS_MODEL", "claude-unapproved-model")
    
    generator = service.synthesize_answer("Query", [{"id": "1", "decision_statement": "Test"}])
    chunks = [json.loads(chunk) async for chunk in generator]
    
    assert len(chunks) == 1
    assert chunks[0]["type"] == "error"
    assert "Configuration error" in chunks[0]["content"]


@pytest.mark.asyncio
async def test_synthesis_fail_loudly_no_key(monkeypatch):
    """Test that synthesis fails if ANTHROPIC_API_KEY is not set."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    
    generator = service.synthesize_answer("Query", [{"id": "1", "decision_statement": "Test"}])
    chunks = [json.loads(chunk) async for chunk in generator]
    
    assert len(chunks) == 1
    assert chunks[0]["type"] == "error"
    assert "Configuration error" in chunks[0]["content"]


@pytest.mark.asyncio
async def test_synthesis_generic_sanitized_error(monkeypatch):
    """Test that external exceptions during streaming are sanitized for the client."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-testkey")
    monkeypatch.setenv("ANTHROPIC_SYNTHESIS_MODEL", "claude-haiku-4-5-20251001")

    # Mock the AsyncAnthropic client creation to throw an exception
    with patch("modules.retrieval.service.AsyncAnthropic") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.messages.create.side_effect = Exception("Internal raw connection failed stack trace database_url")

        generator = service.synthesize_answer("Query", [{"id": "1", "decision_statement": "Test"}])
        chunks = [json.loads(chunk) async for chunk in generator]

        assert len(chunks) == 1
        assert chunks[0]["type"] == "error"
        # Verify message is sanitized and doesn't contain raw exception string
        assert "An error occurred" in chunks[0]["content"]
        assert "Internal raw connection failed" not in chunks[0]["content"]


# ── Router API Tests ───────────────────────────────────────────────────────────

def test_router_ask_jwt_success():
    """POST /ask returns stream when auth JWT is valid."""
    tenant_id = uuid.uuid4()
    
    # Issue valid JWT token
    from modules.auth.service import issue_tenant_jwt
    token = issue_tenant_jwt(user_id="user-123", tenant_id=str(tenant_id), role="member")

    mock_db_pool = MagicMock()
    
    with patch("modules.retrieval.router.get_db_pool", return_value=mock_db_pool), \
         patch("modules.retrieval.service.retrieve_decisions", return_value=[]) as mock_retrieve:
        
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"query": "How is scaling handled?"}
        
        response = client.post("/api/v1/retrieval/ask", json=payload, headers=headers)
        
        assert response.status_code == 200
        mock_retrieve.assert_called_once_with(
            query="How is scaling handled?",
            tenant_id=str(tenant_id),
            filters=None,
            limit=10,
            offset=0,
            pool=mock_db_pool,
        )


def test_router_ask_temp_fallback_success():
    """POST /ask returns stream when JWT is missing/invalid but temporary request-body tenant_id is provided."""
    tenant_id = uuid.uuid4()
    mock_db_pool = MagicMock()

    with patch("modules.retrieval.router.get_db_pool", return_value=mock_db_pool), \
         patch("modules.retrieval.service.retrieve_decisions", return_value=[]) as mock_retrieve:
        
        payload = {
            "query": "How is scaling handled?",
            "tenant_id": str(tenant_id)
        }
        
        response = client.post("/api/v1/retrieval/ask", json=payload)
        
        assert response.status_code == 200
        mock_retrieve.assert_called_once_with(
            query="How is scaling handled?",
            tenant_id=str(tenant_id),
            filters=None,
            limit=10,
            offset=0,
            pool=mock_db_pool,
        )


def test_router_ask_missing_auth():
    """POST /ask returns 401 when JWT is missing and no request-body tenant_id fallback is provided."""
    payload = {"query": "How is scaling handled?"}
    response = client.post("/api/v1/retrieval/ask", json=payload)
    
    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"]
