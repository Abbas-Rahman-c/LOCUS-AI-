"""
Unit tests for modules.ai.triage.classifier.classify().

AsyncAnthropic is mocked completely via modules.ai.triage.classifier's
imported get_anthropic_client (reused from modules.retrieval.service) and
get_triage_model — no network calls are made and no real ANTHROPIC_API_KEY
is required.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest

from modules.ai.triage.classifier import (
    TriageAPIError,
    TriageResultValidationError,
    TriageToolCallError,
    classify,
)
from modules.ai.triage.schemas import TriageDecision, TriageReasonCode
from modules.ingestion.envelope.schemas import EventEnvelope

pytestmark = pytest.mark.asyncio

_FAKE_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages?beta=tools")


def _event(**overrides: object) -> EventEnvelope:
    base = {
        "tenant_id": "13bcd0fa-1ed9-4634-93c7-278ba97ec658",
        "source": "slack",
        "source_id": "1783601758.003909",
        "actor": "U0BGBSV33NG",
        "thread_ref": "C0BFZQ2C9KR",
        "permission_scope": [],
        "raw_content": {"text": "We decided to ship the new pricing page on Friday."},
    }
    base.update(overrides)
    return EventEnvelope(**base)


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


def _patched(message=None, side_effect=None, model="claude-haiku-4-5-20251001"):
    return (
        patch(
            "modules.ai.triage.classifier.get_anthropic_client",
            return_value=_mock_client(message=message, side_effect=side_effect),
        ),
        patch("modules.ai.triage.classifier.get_triage_model", return_value=model),
    )


class TestValidTriageResult:
    async def test_keep_decision_is_returned(self):
        message = _fake_message([
            _tool_use_block(
                "record_triage_result",
                {
                    "decision": TriageDecision.KEEP.value,
                    "confidence": 0.92,
                    "reason_code": TriageReasonCode.EXPLICIT_DECISION.value,
                },
            )
        ])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch:
            result = await classify(_event())
        assert result.decision == TriageDecision.KEEP
        assert result.confidence == 0.92
        assert result.db_triage_result == "kept"

    async def test_discard_decision_maps_to_discarded(self):
        message = _fake_message([
            _tool_use_block(
                "record_triage_result",
                {
                    "decision": TriageDecision.DISCARD.value,
                    "confidence": 0.5,
                    "reason_code": TriageReasonCode.SOCIAL_CHATTER.value,
                },
            )
        ])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch:
            result = await classify(_event())
        assert result.db_triage_result == "discarded"

    async def test_call_kwargs_force_the_tool_choice(self):
        message = _fake_message([
            _tool_use_block(
                "record_triage_result",
                {
                    "decision": TriageDecision.UNCERTAIN.value,
                    "confidence": 0.4,
                    "reason_code": TriageReasonCode.TENTATIVE_PROPOSAL.value,
                },
            )
        ])
        client = _mock_client(message=message)
        with (
            patch("modules.ai.triage.classifier.get_anthropic_client", return_value=client),
            patch("modules.ai.triage.classifier.get_triage_model", return_value="model-x"),
        ):
            await classify(_event())
        _, kwargs = client.beta.tools.messages.create.call_args
        assert kwargs["model"] == "model-x"
        assert kwargs["extra_body"] == {"tool_choice": {"type": "tool", "name": "record_triage_result"}}
        assert kwargs["tools"][0]["name"] == "record_triage_result"


class TestMalformedResponse:
    async def test_missing_tool_use_block_raises(self):
        message = _fake_message([_text_block()])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch, pytest.raises(TriageToolCallError):
            await classify(_event())

    async def test_wrong_tool_name_raises(self):
        message = _fake_message([_tool_use_block("some_other_tool", {})])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch, pytest.raises(TriageToolCallError):
            await classify(_event())

    async def test_invalid_tool_input_raises_validation_error(self):
        message = _fake_message([
            _tool_use_block("record_triage_result", {"decision": "NOT_A_REAL_DECISION"})
        ])
        client_patch, model_patch = _patched(message=message)
        with client_patch, model_patch, pytest.raises(TriageResultValidationError):
            await classify(_event())


class TestAPIFailures:
    async def test_timeout_is_wrapped(self):
        error = anthropic.APITimeoutError(request=_FAKE_REQUEST)
        client_patch, model_patch = _patched(side_effect=error)
        with client_patch, model_patch, pytest.raises(TriageAPIError):
            await classify(_event())

    async def test_connection_error_is_wrapped(self):
        error = anthropic.APIConnectionError(request=_FAKE_REQUEST)
        client_patch, model_patch = _patched(side_effect=error)
        with client_patch, model_patch, pytest.raises(TriageAPIError):
            await classify(_event())
