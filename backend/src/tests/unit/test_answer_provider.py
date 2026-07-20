"""
Unit tests for modules.answering.provider.generate_completion().

AsyncAnthropic is mocked completely via modules.answering.provider's
imported get_anthropic_client / get_synthesis_model (reused from
modules.retrieval.service, not duplicated) — no network calls are made.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest

from modules.answering.provider import (
    AnswerAPIError,
    AnswerResponseValidationError,
    generate_completion,
)

pytestmark = pytest.mark.asyncio

_FAKE_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _fake_message(content: list) -> SimpleNamespace:
    return SimpleNamespace(content=content)


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _mock_client(message=None, side_effect=None) -> MagicMock:
    client = MagicMock()
    if side_effect is not None:
        client.messages.create = AsyncMock(side_effect=side_effect)
    else:
        client.messages.create = AsyncMock(return_value=message)
    return client


def _patched(message=None, side_effect=None, model="claude-haiku-4-5-20251001"):
    return (
        patch(
            "modules.answering.provider.get_anthropic_client",
            return_value=_mock_client(message=message, side_effect=side_effect),
        ),
        patch("modules.answering.provider.get_synthesis_model", return_value=model),
    )


class TestValidResponse:
    async def test_returns_answer_text_and_model(self):
        message = _fake_message(
            [_text_block("Stripe was chosen for self-service billing (Decision 1).")]
        )
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch:
            text, model = await generate_completion("SYSTEM", "USER")
        assert text == "Stripe was chosen for self-service billing (Decision 1)."
        assert model == "claude-haiku-4-5-20251001"

    async def test_call_kwargs_are_forwarded_correctly(self):
        message = _fake_message([_text_block("ok")])
        client = _mock_client(message=message)
        with (
            patch("modules.answering.provider.get_anthropic_client", return_value=client),
            patch("modules.answering.provider.get_synthesis_model", return_value="model-x"),
        ):
            await generate_completion("SYSTEM PROMPT", "USER MESSAGE")
        _, kwargs = client.messages.create.call_args
        assert kwargs["model"] == "model-x"
        assert kwargs["system"] == "SYSTEM PROMPT"
        assert kwargs["messages"] == [{"role": "user", "content": "USER MESSAGE"}]
        assert kwargs["temperature"] == 0
        assert "stream" not in kwargs


class TestMissingConfiguration:
    async def test_missing_anthropic_key_is_wrapped(self):
        with (
            patch(
                "modules.answering.provider.get_anthropic_client",
                side_effect=RuntimeError("ANTHROPIC_API_KEY is not set"),
            ),
            patch("modules.answering.provider.get_synthesis_model", return_value="m"),
        ):
            with pytest.raises(AnswerAPIError):
                await generate_completion("SYSTEM", "USER")


class TestMalformedResponse:
    async def test_missing_text_block_raises_validation_error(self):
        message = _fake_message([SimpleNamespace(type="tool_use", name="x", input={})])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch, pytest.raises(AnswerResponseValidationError):
            await generate_completion("SYSTEM", "USER")

    async def test_empty_content_list_raises_validation_error(self):
        message = _fake_message([])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch, pytest.raises(AnswerResponseValidationError):
            await generate_completion("SYSTEM", "USER")


class TestAPIFailures:
    async def test_timeout_is_wrapped(self):
        error = anthropic.APITimeoutError(request=_FAKE_REQUEST)
        client_patch, model_patch = _patched(side_effect=error)
        with client_patch, model_patch, pytest.raises(AnswerAPIError):
            await generate_completion("SYSTEM", "USER")

    async def test_connection_error_is_wrapped(self):
        error = anthropic.APIConnectionError(request=_FAKE_REQUEST)
        client_patch, model_patch = _patched(side_effect=error)
        with client_patch, model_patch, pytest.raises(AnswerAPIError):
            await generate_completion("SYSTEM", "USER")
