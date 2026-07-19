"""
Unit tests for modules.search.service.search().

Only the two boundary calls are mocked: modules.retrieval.vector.service.
search() (Voyage + DB) and modules.answering.service.generate_answer()
(Claude). PermissionService.filter_accessible_decisions() and
ContextService.build_context() run for real - this test exercises the
actual reused pipeline, not a re-implementation of it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from modules.answering.schemas import AnswerResult
from modules.retrieval.vector.schemas import RetrievalMatch
from modules.search.service import search

pytestmark = pytest.mark.asyncio

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


def _patched(matches, answer_result):
    return (
        patch(
            "modules.search.service.vector_search",
            AsyncMock(return_value=(matches, 1024)),
        ),
        patch("modules.search.service.generate_answer", AsyncMock(return_value=answer_result)),
    )


class TestSuccessfulSearch:
    async def test_returns_answer_citations_and_metadata(self):
        match = _match()
        answer_result = AnswerResult(
            answer="We chose Stripe for self-service billing (Decision 1).",
            citations=[1],
            model="claude-haiku-test",
            latency_ms=12.5,
        )
        retrieval_patch, answer_patch = _patched([match], answer_result)

        with retrieval_patch, answer_patch:
            result = await search(object(), TENANT, "Why did we choose Stripe?", ["team:billing"], 5)

        assert result.answer == "We chose Stripe for self-service billing (Decision 1)."
        assert result.metadata.retrieved_count == 1
        assert result.metadata.authorized_count == 1
        assert result.metadata.decision_count == 1
        assert result.metadata.model == "claude-haiku-test"
        assert result.metadata.latency_ms == 12.5
        assert result.metadata.token_estimate > 0

    async def test_vector_search_called_with_tenant_id_not_a_request_field(self):
        """Proof tenant_id flows into retrieval as a plain authenticated
        parameter, never derived from anything client-suppliable."""
        match = _match()
        answer_result = AnswerResult(answer="ok", citations=[], model="m", latency_ms=1.0)
        retrieval_patch, answer_patch = _patched([match], answer_result)
        pool = object()

        with retrieval_patch as vector_mock, answer_patch:
            await search(pool, TENANT, "Why did we choose Stripe?", ["team:billing"], 5)

        vector_mock.assert_awaited_once_with(pool, TENANT, "Why did we choose Stripe?", 5)


class TestNoMatchingDecisions:
    async def test_empty_retrieval_produces_empty_citations_and_zero_counts(self):
        answer_result = AnswerResult(
            answer="I couldn't find enough information in the available decisions.",
            citations=[],
            model="claude-haiku-test",
            latency_ms=1.0,
        )
        retrieval_patch, answer_patch = _patched([], answer_result)

        with retrieval_patch, answer_patch:
            result = await search(object(), TENANT, "Why did we choose Stripe?", ["team:billing"], 5)

        assert result.citations == []
        assert result.metadata.retrieved_count == 0
        assert result.metadata.authorized_count == 0
        assert result.metadata.decision_count == 0


class TestPermissionScopeFiltering:
    async def test_wrong_scope_is_excluded_even_within_the_tenant(self):
        """Every match here already shares TENANT (RLS's job is done) - only
        permission_scope should decide what survives."""
        match = _match(permission_scope=["team:sales"])
        answer_result = AnswerResult(answer="ok", citations=[], model="m", latency_ms=1.0)
        retrieval_patch, answer_patch = _patched([match], answer_result)

        with retrieval_patch, answer_patch:
            result = await search(object(), TENANT, "Why did we choose Stripe?", ["team:billing"], 5)

        assert result.metadata.authorized_count == 0

    async def test_matching_scope_is_included(self):
        match = _match(permission_scope=["team:billing"])
        answer_result = AnswerResult(
            answer="Per Decision 1.", citations=[1], model="m", latency_ms=1.0
        )
        retrieval_patch, answer_patch = _patched([match], answer_result)

        with retrieval_patch, answer_patch:
            result = await search(object(), TENANT, "Why did we choose Stripe?", ["team:billing"], 5)

        assert result.metadata.authorized_count == 1
        assert len(result.citations) == 1


class TestCitationValidation:
    async def test_cited_number_resolves_to_correct_authorized_decision(self):
        first = _match(decision_statement="Use Stripe", confidence=0.94)
        second = _match(decision_statement="Use Postgres", confidence=0.8)
        answer_result = AnswerResult(
            answer="Per Decision 2, we use Postgres.", citations=[2], model="m", latency_ms=1.0
        )
        retrieval_patch, answer_patch = _patched([first, second], answer_result)

        with retrieval_patch, answer_patch:
            result = await search(
                object(), TENANT, "Why did we choose Postgres?", ["team:billing"], 5
            )

        assert len(result.citations) == 1
        citation = result.citations[0]
        assert citation.decision_number == 2
        assert citation.decision_id == second.decision_id
        assert citation.decision_statement == "Use Postgres"
        assert citation.confidence == 0.8

    async def test_out_of_range_citation_is_skipped_not_fabricated(self):
        match = _match()
        answer_result = AnswerResult(
            answer="Per Decision 99, ...", citations=[99], model="m", latency_ms=1.0
        )
        retrieval_patch, answer_patch = _patched([match], answer_result)

        with retrieval_patch, answer_patch:
            result = await search(object(), TENANT, "Why did we choose Stripe?", ["team:billing"], 5)

        assert result.citations == []


class TestGroundedRefusal:
    async def test_no_authorized_decisions_yields_refusal_with_no_citations(self):
        match = _match(permission_scope=["team:sales"])  # will be filtered out
        answer_result = AnswerResult(
            answer="I couldn't find enough information in the available decisions.",
            citations=[],
            model="m",
            latency_ms=1.0,
        )
        retrieval_patch, answer_patch = _patched([match], answer_result)

        with retrieval_patch, answer_patch as answer_mock:
            result = await search(object(), TENANT, "Why did we choose Stripe?", ["team:billing"], 5)

        # Context passed to Claude must be divider-only (no authorized decisions)
        (_, context_arg), _ = answer_mock.call_args
        assert "Decision 1" not in context_arg
        assert result.answer == "I couldn't find enough information in the available decisions."
        assert result.citations == []
