"""
Unit tests for modules.digest.service.generate_team_pulse().

Only the two boundary calls are mocked: modules.retrieval.vector.service.
search() (Voyage + DB) and modules.answering.service.generate_answer()
(Claude). filter_accessible_decisions() and build_context() run for real —
same pattern as test_search_service.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from modules.answering.schemas import AnswerResult
from modules.digest.schemas import DigestResponse
from modules.digest.service import _DIGEST_TOP_K, generate_team_pulse
from modules.retrieval.vector.schemas import RetrievalMatch

pytestmark = pytest.mark.asyncio

TENANT = uuid4()


def _answer(**overrides) -> AnswerResult:
    fields = {
        "answer": "ok",
        "reasoning": "grounded",
        "citations": [],
        "confidence": 0.9,
        "sufficient_evidence": True,
        "model": "m",
        "latency_ms": 1.0,
    }
    fields.update(overrides)
    return AnswerResult(**fields)


def _match(**overrides) -> RetrievalMatch:
    fields = {
        "decision_id": uuid4(),
        "decision_statement": "We chose Stripe for PCI-compliant billing.",
        "similarity_score": 0.87,
        "confidence": 0.94,
        "tenant_id": TENANT,
        "permission_scope": [],  # workspace-wide — visible to all
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
            "modules.digest.service.vector_search",
            AsyncMock(return_value=(matches, 1024)),
        ),
        patch(
            "modules.digest.service.generate_answer",
            AsyncMock(return_value=answer_result),
        ),
    )


class TestTeamScope:
    async def test_returns_digest_response_with_expected_shape(self):
        match = _match()
        answer_result = _answer(
            answer="This week the team decided to use Stripe.",
            model="claude-test",
            latency_ms=42.0,
        )
        retrieval_patch, answer_patch = _patched([match], answer_result)

        with retrieval_patch, answer_patch:
            result = await generate_team_pulse(object(), TENANT, [], scope="team")

        assert isinstance(result, DigestResponse)
        assert result.scope == "team"
        assert result.summary == "This week the team decided to use Stripe."
        assert len(result.items) == 1
        assert result.items[0].decision_statement == match.decision_statement
        assert result.items[0].confidence == match.confidence
        assert result.metadata.model == "claude-test"
        assert result.metadata.latency_ms == 42.0
        assert result.metadata.decision_count == 1

    async def test_period_string_is_a_date_range(self):
        answer_result = _answer()
        retrieval_patch, answer_patch = _patched([_match()], answer_result)

        with retrieval_patch, answer_patch:
            result = await generate_team_pulse(object(), TENANT, [], scope="team")

        # e.g. "2026-07-17/2026-07-24"
        parts = result.period.split("/")
        assert len(parts) == 2
        assert len(parts[0]) == 10  # YYYY-MM-DD
        assert len(parts[1]) == 10

    async def test_vector_search_called_with_digest_top_k(self):
        """Digest must retrieve more decisions than a point query."""
        answer_result = _answer()
        retrieval_patch, answer_patch = _patched([], answer_result)

        with retrieval_patch as vector_mock, answer_patch:
            await generate_team_pulse(object(), TENANT, [], scope="team")

        _, _, _, top_k_arg = vector_mock.await_args.args
        assert top_k_arg == _DIGEST_TOP_K


class TestPersonalScope:
    async def test_returns_personal_scope_in_response(self):
        answer_result = _answer(answer="Your decisions this week.")
        retrieval_patch, answer_patch = _patched([_match()], answer_result)

        with retrieval_patch, answer_patch:
            result = await generate_team_pulse(object(), TENANT, [], scope="personal")

        assert result.scope == "personal"
        # No actors.auth_user_id linkage → falls back to team-wide question
        assert result.metadata.personalized is False

    async def test_uses_named_question_when_actor_resolves(self):
        """When actors.auth_user_id links, personal scope asks about that person."""
        answer_result = _answer()

        team_retrieval_patch, team_answer_patch = _patched([], answer_result)
        personal_retrieval_patch, personal_answer_patch = _patched([], answer_result)

        with team_retrieval_patch, team_answer_patch as team_answer_mock:
            await generate_team_pulse(object(), TENANT, [], scope="team")
        team_question = team_answer_mock.await_args.args[0]

        with (
            personal_retrieval_patch,
            personal_answer_patch as personal_answer_mock,
            patch(
                "modules.digest.service._resolve_caller_actor",
                AsyncMock(return_value="Jane Doe"),
            ),
        ):
            await generate_team_pulse(
                object(), TENANT, [], scope="personal", user_id=uuid4()
            )
        personal_question = personal_answer_mock.await_args.args[0]

        assert team_question != personal_question
        assert "Jane Doe" in personal_question


class TestEmptyResults:
    async def test_empty_retrieval_produces_empty_items(self):
        answer_result = _answer(answer="No decisions were found this week.")
        retrieval_patch, answer_patch = _patched([], answer_result)

        with retrieval_patch, answer_patch:
            result = await generate_team_pulse(object(), TENANT, [], scope="team")

        assert result.items == []
        assert result.metadata.decision_count == 0


class TestPermissionFiltering:
    async def test_scoped_decision_excluded_with_no_resolved_scopes(self):
        """A decision with permission_scope=['team:billing'] must be filtered
        out when the caller has no resolved scopes — same Layer 2 guarantee
        as /search."""
        scoped = _match(permission_scope=["team:billing"])
        answer_result = _answer()
        retrieval_patch, answer_patch = _patched([scoped], answer_result)

        with retrieval_patch, answer_patch:
            result = await generate_team_pulse(object(), TENANT, [], scope="team")

        assert result.items == []
        assert result.metadata.decision_count == 0

    async def test_workspace_wide_decision_surfaces_with_no_resolved_scopes(self):
        workspace_wide = _match(permission_scope=[])
        answer_result = _answer()
        retrieval_patch, answer_patch = _patched([workspace_wide], answer_result)

        with retrieval_patch, answer_patch:
            result = await generate_team_pulse(object(), TENANT, [], scope="team")

        assert len(result.items) == 1


class TestDigestWeekHelpers:
    def test_digest_week_of_is_monday(self):
        from datetime import datetime, timezone

        from modules.digest.store import digest_week_of

        # Wednesday 2026-07-22 → week_of Monday 2026-07-20
        wed = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
        assert digest_week_of(wed).isoformat() == "2026-07-20"

    def test_digest_week_of_before_monday_0900_uses_previous(self):
        from datetime import datetime, timezone

        from modules.digest.store import digest_week_of

        mon_early = datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc)
        assert digest_week_of(mon_early).isoformat() == "2026-07-13"

    def test_digest_week_of_monday_after_0900_is_today(self):
        from datetime import datetime, timezone

        from modules.digest.store import digest_week_of

        mon_late = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
        assert digest_week_of(mon_late).isoformat() == "2026-07-20"
