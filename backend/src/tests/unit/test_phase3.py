"""
Phase 3 — Feedback Loop tests (Rebira's scope).

Covers:
  1. POST /feedback  — valid thumbs-up persists to DB
  2. POST /feedback  — valid thumbs-down with comment persists to DB
  3. POST /feedback  — invalid signal is rejected (400)
  4. POST /feedback  — graceful fallback when DB pool is down
"""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-for-unit-tests")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth.service import issue_tenant_jwt
from modules.feedback.router import router as feedback_router

app = FastAPI()
app.include_router(feedback_router)

client = TestClient(app)

TEST_TENANT_ID = "00000000-0000-0000-0000-000000000000"


def _auth_headers(tenant_id: str = TEST_TENANT_ID) -> dict:
    token = issue_tenant_jwt(user_id="test-user", tenant_id=tenant_id, role="member")
    return {"Authorization": f"Bearer {token}"}


def _mock_tenant_connection(mock_conn):
    return MagicMock(
        __aenter__=AsyncMock(return_value=mock_conn),
        __aexit__=AsyncMock(return_value=False),
    )


# ── Feedback endpoint tests ──────────────────────────────────────────

@patch("modules.feedback.service.get_db_pool")
@patch("modules.feedback.service.tenant_conn")
def test_feedback_thumbs_up_persists(mock_tenant_conn, mock_get_db_pool):
    """A valid 'up' signal should INSERT into feedback_events."""
    mock_conn = AsyncMock()
    mock_tenant_conn.return_value = _mock_tenant_connection(mock_conn)

    payload = {
        "query": "What architecture did we pick?",
        "synthesized_answer": "We chose microservices [Decision 1].",
        "signal": "up",
    }

    response = client.post("/feedback", json=payload, headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_conn.execute.assert_called_once()
    args = mock_conn.execute.call_args[0]
    assert args[1] == TEST_TENANT_ID
    assert args[2] == payload["query"]
    assert args[3] == payload["synthesized_answer"]
    assert args[4] == "up"


@patch("modules.feedback.service.get_db_pool")
@patch("modules.feedback.service.tenant_conn")
def test_feedback_thumbs_down_persists(mock_tenant_conn, mock_get_db_pool):
    """A valid 'down' signal should also INSERT into feedback_events."""
    mock_conn = AsyncMock()
    mock_tenant_conn.return_value = _mock_tenant_connection(mock_conn)

    payload = {
        "query": "What DB do we use?",
        "synthesized_answer": "Postgres with pgvector.",
        "signal": "down",
        "comment": "Answer was vague",
    }

    response = client.post("/feedback", json=payload, headers=_auth_headers())

    assert response.status_code == 200
    args = mock_conn.execute.call_args[0]
    assert args[4] == "down"
    assert args[5] == "Answer was vague"


def test_feedback_rejects_invalid_signal():
    """Signals other than 'up' / 'down' must be rejected with 400."""
    payload = {
        "query": "Test query",
        "synthesized_answer": "Test answer",
        "signal": "invalid",
    }

    response = client.post("/feedback", json=payload, headers=_auth_headers())

    assert response.status_code == 400
    assert response.json()["detail"] == "Signal must be 'up' or 'down'"


@patch(
    "modules.feedback.service.get_db_pool",
    side_effect=RuntimeError("Database pool not initialized"),
)
def test_feedback_graceful_when_db_is_down(mock_get_db_pool):
    """When the DB pool is unavailable, feedback should still return 200 (logged, not lost)."""
    payload = {
        "query": "Any question",
        "synthesized_answer": "Some answer",
        "signal": "down",
    }

    response = client.post("/feedback", json=payload, headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["status"] == "success"
