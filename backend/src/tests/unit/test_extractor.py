"""
Unit tests for modules.ai.extraction.extractor.extract().

AsyncAnthropic is mocked completely via modules.ai.extraction.extractor's
imported get_anthropic_client (reused from modules.retrieval.service) and
get_extraction_model — no network calls are made.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest

from modules.ai.extraction.extractor import (
    ExtractionAPIError,
    ExtractionResultValidationError,
    ExtractionToolCallError,
    extract,
)
from modules.ai.extraction.schemas import ActorRole, DecisionStatus, RecordType
from modules.ingestion.envelope.schemas import EventEnvelope

pytestmark = pytest.mark.asyncio

_FAKE_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages?beta=tools")


def _event(**overrides: object) -> EventEnvelope:
    base = {
        "tenant_id": "13bcd0fa-1ed9-4634-93c7-278ba97ec658",
        "source": "gmail",
        "source_id": "18d1234abcd",
        "actor": "alice@example.com",
        "thread_ref": None,
        "permission_scope": [],
        "raw_content": {"subject": "Re: pricing", "body": "We decided to ship Friday."},
    }
    base.update(overrides)
    return EventEnvelope(**base)


def _valid_input(**overrides: object) -> dict:
    base = {
        "record_type": RecordType.DECISION.value,
        "status": DecisionStatus.DECIDED.value,
        "decision_statement": "Ship the new pricing page on Friday.",
        "rationale": None,
        "alternatives_considered": [],
        "actors": [],
        "confidence": 0.9,
    }
    base.update(overrides)
    return base


def _tool_use_block(name: str, input_: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=name, input=input_, id="toolu_123")


def _text_block(text: str = "hello") -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _fake_message(content: list) -> SimpleNamespace:
    return SimpleNamespace(content=content)


def _mock_client(message=None, side_effect=None) -> MagicMock:
    client = MagicMock()
    if side_effect is not None:
        client.beta.tools.messages.create = AsyncMock(side_effect=side_effect)
    else:
        client.beta.tools.messages.create = AsyncMock(return_value=message)
    return client


def _patched(message=None, side_effect=None, model="claude-sonnet-4-5-20250929"):
    return (
        patch(
            "modules.ai.extraction.extractor.get_anthropic_client",
            return_value=_mock_client(message=message, side_effect=side_effect),
        ),
        patch("modules.ai.extraction.extractor.get_extraction_model", return_value=model),
    )


class TestValidExtractionResult:
    async def test_returns_validated_extraction(self):
        message = _fake_message([
            _tool_use_block("record_extraction_result", _valid_input())
        ])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch:
            result = await extract(_event())
        assert result.record_type == RecordType.DECISION
        assert result.decision_statement == "Ship the new pricing page on Friday."
        assert result.actors == []

    async def test_actors_and_rationale_are_carried_through(self):
        message = _fake_message([
            _tool_use_block(
                "record_extraction_result",
                _valid_input(
                    rationale="Marketing needs it live before the campaign.",
                    actors=[{"source_actor_id": "alice@example.com", "role": ActorRole.DECIDED_BY.value}],
                ),
            )
        ])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch:
            result = await extract(_event())
        assert result.rationale == "Marketing needs it live before the campaign."
        assert result.actors[0].source_actor_id == "alice@example.com"
        assert result.actors[0].role == ActorRole.DECIDED_BY

    async def test_call_kwargs_force_the_tool_choice(self):
        message = _fake_message([
            _tool_use_block("record_extraction_result", _valid_input())
        ])
        client = _mock_client(message=message)
        with (
            patch("modules.ai.extraction.extractor.get_anthropic_client", return_value=client),
            patch("modules.ai.extraction.extractor.get_extraction_model", return_value="model-x"),
        ):
            await extract(_event())
        _, kwargs = client.beta.tools.messages.create.call_args
        assert kwargs["model"] == "model-x"
        assert kwargs["extra_body"] == {
            "tool_choice": {"type": "tool", "name": "record_extraction_result"}
        }


class TestMalformedResponse:
    async def test_missing_tool_use_block_raises(self):
        message = _fake_message([_text_block()])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch, pytest.raises(ExtractionToolCallError):
            await extract(_event())

    async def test_wrong_tool_name_raises(self):
        message = _fake_message([_tool_use_block("some_other_tool", {})])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch, pytest.raises(ExtractionToolCallError):
            await extract(_event())

    async def test_two_decided_by_actors_raises_validation_error(self):
        message = _fake_message([
            _tool_use_block(
                "record_extraction_result",
                _valid_input(
                    actors=[
                        {"source_actor_id": "a", "role": ActorRole.DECIDED_BY.value},
                        {"source_actor_id": "b", "role": ActorRole.DECIDED_BY.value},
                    ]
                ),
            )
        ])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch, pytest.raises(ExtractionResultValidationError):
            await extract(_event())

    async def test_missing_required_field_raises_validation_error(self):
        bad_input = _valid_input()
        del bad_input["confidence"]
        message = _fake_message([
            _tool_use_block("record_extraction_result", bad_input)
        ])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch, pytest.raises(ExtractionResultValidationError):
            await extract(_event())


class TestAPIFailures:
    async def test_timeout_is_wrapped(self):
        error = anthropic.APITimeoutError(request=_FAKE_REQUEST)
        client_patch, model_patch = _patched(side_effect=error)
        with client_patch, model_patch, pytest.raises(ExtractionAPIError):
            await extract(_event())

    async def test_connection_error_is_wrapped(self):
        error = anthropic.APIConnectionError(request=_FAKE_REQUEST)
        client_patch, model_patch = _patched(side_effect=error)
        with client_patch, model_patch, pytest.raises(ExtractionAPIError):
            await extract(_event())
