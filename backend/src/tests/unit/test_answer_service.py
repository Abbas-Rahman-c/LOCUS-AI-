"""
Unit tests for modules.answering.service.generate_answer().

modules.answering.provider.generate_completion() is mocked completely via
modules.answering.service's imported name — no real Anthropic API call is
made.
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

from modules.answering.schemas import AnswerResult
from modules.answering.service import _extract_citations, generate_answer


def _patched(answer_text: str, model: str = "claude-haiku-test"):
    return patch(
        "modules.answering.service.generate_completion",
        AsyncMock(return_value=(answer_text, model)),
    )


class TestNormalAnswer:
    pytestmark = pytest.mark.asyncio

    async def test_returns_answer_result_with_expected_fields(self):
        with _patched("We chose Stripe for self-service billing (Decision 1)."):
            result = await generate_answer("Why did we choose Stripe?", "some context")

        assert isinstance(result, AnswerResult)
        assert result.answer == "We chose Stripe for self-service billing (Decision 1)."
        assert result.citations == [1]
        assert result.model == "claude-haiku-test"
        assert result.latency_ms >= 0

    async def test_passes_question_and_context_to_prompt_builder(self):
        completion_mock = AsyncMock(return_value=("answer", "claude-haiku-test"))
        with patch("modules.answering.service.generate_completion", completion_mock):
            await generate_answer("Why did we choose Stripe?", "Decision 1 context")
        (system_prompt, user_message), _ = completion_mock.call_args
        assert "You are Locus AI." in system_prompt
        assert "Why did we choose Stripe?" in user_message
        assert "Decision 1 context" in user_message


class TestNoContext:
    pytestmark = pytest.mark.asyncio

    async def test_refusal_answer_has_no_citations(self):
        with _patched("I couldn't find enough information in the available decisions."):
            result = await generate_answer("Why did we choose Stripe?", "")
        assert result.citations == []


class TestLargeContext:
    pytestmark = pytest.mark.asyncio

    async def test_handles_large_context_without_error(self):
        large_context = "Decision block text. " * 10000
        with _patched("Answer grounded in many decisions (Decision 1, Decision 42)."):
            result = await generate_answer("Why did we choose Stripe?", large_context)
        assert result.citations == [1, 42]


class TestCitationFormatting:
    def test_single_citation(self):
        assert _extract_citations("See Decision 1 for details.") == [1]

    def test_multiple_citations_are_deduped_and_sorted(self):
        assert _extract_citations("Decision 3 and Decision 1, also Decision 3 again.") == [1, 3]

    def test_case_insensitive_citation(self):
        assert _extract_citations("As shown in decision 2.") == [2]

    def test_no_citations_returns_empty_list(self):
        assert (
            _extract_citations("I couldn't find enough information in the available decisions.")
            == []
        )


class TestLogging:
    pytestmark = pytest.mark.asyncio

    async def test_logs_model_citations_and_latency(self, caplog):
        with caplog.at_level(logging.INFO, logger="modules.answering.service"):
            with _patched("Chosen per Decision 1."):
                await generate_answer("Why did we choose Stripe?", "context")

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "model=claude-haiku-test" in message
        assert "citations=[1]" in message
        assert "latency_ms=" in message
