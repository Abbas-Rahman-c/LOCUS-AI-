"""
Unit tests for queues.workers.event_worker._handle_message().

is_duplicate/mark_seen/process_and_persist_event are all mocked at their
event_worker.py import sites - no real database, pgmq, Claude, or Voyage
call is made.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from modules.ai.pipeline.schemas import IngestionProcessingResult
from modules.ai.triage.schemas import TriageDecision, TriageReasonCode, TriageResult
from queues.pgmq.queues import QueueName
from queues.workers.event_worker import _handle_message

pytestmark = pytest.mark.asyncio

TENANT = uuid.uuid4()
RAW_EVENT_ID = uuid.uuid4()
DECISION_ID = uuid.uuid4()


def _envelope_payload(**overrides) -> dict:
    base = {
        "tenant_id": str(TENANT),
        "source": "gmail",
        "source_id": "18d1234abcd",
        "actor": "alice@example.com",
        "permission_scope": [],
        "raw_content": {"subject": "Re: pricing", "body": "We decided to ship Friday."},
    }
    base.update(overrides)
    return base


def _msg(msg_id=1, **overrides):
    return {"msg_id": msg_id, "message": _envelope_payload(**overrides)}


def _result(persisted=True, decision_id=DECISION_ID, decision=TriageDecision.KEEP):
    return IngestionProcessingResult(
        triage=TriageResult(decision=decision, confidence=0.9, reason_code=TriageReasonCode.EXPLICIT_DECISION),
        extraction=None if decision == TriageDecision.DISCARD else _fake_extraction(),
        decision_id=None if decision == TriageDecision.DISCARD else decision_id,
        persisted=persisted if decision != TriageDecision.DISCARD else False,
        embedding_enqueued=persisted if decision != TriageDecision.DISCARD else False,
    )


def _fake_extraction():
    from modules.ai.extraction.schemas import DecisionStatus, ExtractionResult, RecordType

    return ExtractionResult(
        record_type=RecordType.DECISION,
        status=DecisionStatus.DECIDED,
        decision_statement="Ship Friday.",
        confidence=0.9,
    )


def _client():
    client = MagicMock()
    client.delete = AsyncMock()
    return client


class TestMalformedPayload:
    async def test_non_json_string_payload_is_left_in_queue(self):
        client = _client()
        msg = {"msg_id": 1, "message": "{not-json"}
        await _handle_message(client, object(), msg)
        client.delete.assert_not_awaited()


class TestInvalidEnvelope:
    async def test_invalid_envelope_is_left_in_queue(self):
        client = _client()
        msg = _msg(source_id=None)  # required field missing
        with patch("queues.workers.event_worker.is_duplicate", AsyncMock()) as dup_mock:
            await _handle_message(client, object(), msg)
        dup_mock.assert_not_awaited()
        client.delete.assert_not_awaited()


class TestDuplicateHandling:
    async def test_duplicate_found_up_front_is_deleted_without_running_pipeline(self):
        client = _client()
        with (
            patch("queues.workers.event_worker.is_duplicate", AsyncMock(return_value=True)),
            patch("queues.workers.event_worker.mark_seen", AsyncMock()) as mark_seen_mock,
            patch("queues.workers.event_worker.process_and_persist_event", AsyncMock()) as pipeline_mock,
        ):
            await _handle_message(client, object(), _msg())

        mark_seen_mock.assert_not_awaited()
        pipeline_mock.assert_not_awaited()
        client.delete.assert_awaited_once_with(QueueName.INGESTION, 1)

    async def test_duplicate_on_insert_race_is_deleted_without_running_pipeline(self):
        client = _client()
        with (
            patch("queues.workers.event_worker.is_duplicate", AsyncMock(return_value=False)),
            patch("queues.workers.event_worker.mark_seen", AsyncMock(return_value=None)),
            patch("queues.workers.event_worker.process_and_persist_event", AsyncMock()) as pipeline_mock,
        ):
            await _handle_message(client, object(), _msg())

        pipeline_mock.assert_not_awaited()
        client.delete.assert_awaited_once_with(QueueName.INGESTION, 1)


class TestDedupFailureIsRetryable:
    async def test_dedup_check_error_leaves_message_in_queue(self):
        client = _client()
        with patch("queues.workers.event_worker.is_duplicate", AsyncMock(side_effect=RuntimeError("db down"))):
            await _handle_message(client, object(), _msg())
        client.delete.assert_not_awaited()


class TestSuccessfulProcessing:
    async def test_keep_runs_full_pipeline_and_deletes_message(self):
        client = _client()
        with (
            patch("queues.workers.event_worker.is_duplicate", AsyncMock(return_value=False)),
            patch("queues.workers.event_worker.mark_seen", AsyncMock(return_value=RAW_EVENT_ID)),
            patch(
                "queues.workers.event_worker.process_and_persist_event",
                AsyncMock(return_value=_result(decision=TriageDecision.KEEP)),
            ) as pipeline_mock,
        ):
            await _handle_message(client, object(), _msg())

        pipeline_mock.assert_awaited_once()
        _, kwargs = pipeline_mock.call_args
        assert kwargs["origin_raw_event_id"] == RAW_EVENT_ID
        client.delete.assert_awaited_once_with(QueueName.INGESTION, 1)

    async def test_discard_still_deletes_message_after_pipeline_runs(self):
        """DISCARD is a successful, terminal outcome - not a failure - so
        the message is still deleted."""
        client = _client()
        with (
            patch("queues.workers.event_worker.is_duplicate", AsyncMock(return_value=False)),
            patch("queues.workers.event_worker.mark_seen", AsyncMock(return_value=RAW_EVENT_ID)),
            patch(
                "queues.workers.event_worker.process_and_persist_event",
                AsyncMock(return_value=_result(decision=TriageDecision.DISCARD)),
            ),
        ):
            await _handle_message(client, object(), _msg())

        client.delete.assert_awaited_once_with(QueueName.INGESTION, 1)


class TestPipelineFailureIsRetryable:
    async def test_pipeline_error_leaves_message_in_queue(self):
        client = _client()
        with (
            patch("queues.workers.event_worker.is_duplicate", AsyncMock(return_value=False)),
            patch("queues.workers.event_worker.mark_seen", AsyncMock(return_value=RAW_EVENT_ID)),
            patch(
                "queues.workers.event_worker.process_and_persist_event",
                AsyncMock(side_effect=RuntimeError("claude timeout")),
            ),
        ):
            await _handle_message(client, object(), _msg())

        client.delete.assert_not_awaited()
