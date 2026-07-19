"""
Integration tests for modules.search.router's POST /search (Phase 2
production search endpoint), through the real app.main ASGI app.

modules.search.service.vector_search() and .generate_answer() are mocked
at their modules.search.service import sites (no real Voyage/Anthropic/DB
call); permission filtering and context building run for real. Auth uses
real issue_tenant_jwt()-signed tokens, matching the pattern already
established in tests/unit/test_retrieval.py's router tests.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from modules.answering.schemas import AnswerResult
from modules.auth.service import issue_tenant_jwt
from modules.retrieval.vector.schemas import RetrievalMatch

client = TestClient(app)

TENANT = uuid4()


def _match(**overrides) -> RetrievalMatch:
    fields = {
        "decision_id": uuid4(),
        "decision_statement": "We chose Stripe for PCI-compliant billing.",
        "similarity_score": 0.87,
        "confidence": 0.94,
        "tenant_id": TENANT,
        "permission_scope": ["team:billing"],
        "rationale": "Supports self-service billing.",
        "alternatives_considered": ["Paddle"],
        "created_at": datetime(2026, 7, 19, tzinfo=timezone.utc),
        "decision_type": "decision",
        "owner": "Jane Doe",
    }
    fields.update(overrides)
    return RetrievalMatch(**fields)


def _auth_headers(tenant_id=TENANT, role="member"):
    token = issue_tenant_jwt(user_id="user-123", tenant_id=str(tenant_id), role=role)
    return {"Authorization": f"Bearer {token}"}


def _request_body(**overrides):
    body = {"question": "Why did we choose Stripe?", "permission_scopes": ["team:billing"]}
    body.update(overrides)
    return body


def _patched(matches, answer_result):
    mock_pool = MagicMock()
    return (
        patch("modules.search.router.get_db_pool", return_value=mock_pool),
        patch(
            "modules.search.service.vector_search", AsyncMock(return_value=(matches, 1024))
        ),
        patch("modules.search.service.generate_answer", AsyncMock(return_value=answer_result)),
    )


class TestSearchEndpointMountedExactlyOnce:
    def test_mounted_exactly_once_as_post(self):
        matches = [
            (route.path, method)
            for route in app.routes
            for method in getattr(route, "methods", set())
            if route.path == "/search"
        ]
        assert matches == [("/search", "POST")]


class TestAuthenticationRequired:
    def test_missing_jwt_is_rejected(self):
        response = client.post("/search", json=_request_body())
        assert response.status_code in (401, 403)

    def test_invalid_jwt_is_rejected(self):
        response = client.post(
            "/search", json=_request_body(), headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert response.status_code == 401

    def test_client_supplied_tenant_id_in_body_is_rejected_as_unknown_field(self):
        """SearchRequest has extra="forbid" and no tenant_id field at all -
        a client cannot spoof tenant_id even by trying to add one."""
        pool_patch, vector_patch, answer_patch = _patched([], AnswerResult(
            answer="ok", citations=[], model="m", latency_ms=1.0
        ))
        with pool_patch, vector_patch, answer_patch:
            response = client.post(
                "/search",
                json={**_request_body(), "tenant_id": str(uuid4())},
                headers=_auth_headers(),
            )
        assert response.status_code == 422


class TestSuccessfulResponse:
    def test_returns_answer_citations_and_metadata(self):
        match = _match()
        answer_result = AnswerResult(
            answer="We chose Stripe for self-service billing (Decision 1).",
            citations=[1],
            model="claude-haiku-test",
            latency_ms=12.5,
        )
        pool_patch, vector_patch, answer_patch = _patched([match], answer_result)

        with pool_patch, vector_patch, answer_patch:
            response = client.post("/search", json=_request_body(), headers=_auth_headers())

        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "We chose Stripe for self-service billing (Decision 1)."
        assert body["metadata"]["retrieved_count"] == 1
        assert body["metadata"]["authorized_count"] == 1
        assert body["metadata"]["decision_count"] == 1
        assert len(body["citations"]) == 1
        assert body["citations"][0]["decision_id"] == str(match.decision_id)
        assert body["citations"][0]["decision_statement"] == match.decision_statement


class TestTenantIdDerivedFromAuth:
    def test_search_uses_authenticated_tenant_not_a_client_value(self):
        """Proof: the tenant the vector search actually runs against comes
        from the JWT, not from anything in the request body (which has no
        tenant_id field to begin with)."""
        answer_result = AnswerResult(answer="ok", citations=[], model="m", latency_ms=1.0)
        pool_patch, vector_patch, answer_patch = _patched([], answer_result)

        with pool_patch, vector_patch as vector_mock, answer_patch:
            client.post("/search", json=_request_body(), headers=_auth_headers(tenant_id=TENANT))

        (_pool, tenant_arg, _question, _top_k), _ = vector_mock.call_args
        # TenantContext.tenant_id is a str (a JWT claim) - compare accordingly.
        assert str(tenant_arg) == str(TENANT)


class TestNoMatchingDecisions:
    def test_empty_retrieval_returns_refusal_and_zero_counts(self):
        answer_result = AnswerResult(
            answer="I couldn't find enough information in the available decisions.",
            citations=[],
            model="claude-haiku-test",
            latency_ms=1.0,
        )
        pool_patch, vector_patch, answer_patch = _patched([], answer_result)

        with pool_patch, vector_patch, answer_patch:
            response = client.post("/search", json=_request_body(), headers=_auth_headers())

        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["retrieved_count"] == 0
        assert body["citations"] == []


class TestPermissionScopeFiltering:
    def test_wrong_scope_decisions_are_excluded(self):
        match = _match(permission_scope=["team:sales"])
        answer_result = AnswerResult(answer="ok", citations=[], model="m", latency_ms=1.0)
        pool_patch, vector_patch, answer_patch = _patched([match], answer_result)

        with pool_patch, vector_patch, answer_patch:
            response = client.post("/search", json=_request_body(), headers=_auth_headers())

        assert response.json()["metadata"]["authorized_count"] == 0


class TestValidation:
    def test_blank_question_is_rejected(self):
        response = client.post(
            "/search", json=_request_body(question=""), headers=_auth_headers()
        )
        assert response.status_code == 422
