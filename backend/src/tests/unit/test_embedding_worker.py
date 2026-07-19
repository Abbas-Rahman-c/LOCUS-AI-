"""
Unit tests for queues.workers.embedding_worker._handle_message().

PgmqClient and process_embedding_job() are both mocked - no real pgmq or
database call is made.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from modules.ai.embeddings.service import DecisionNotFoundError
from queues.pgmq.queues import QueueName
from queues.workers.embedding_worker import _handle_message

pytestmark = pytest.mark.asyncio

TENANT = uuid.uuid4()
DECISION_ID = uuid.uuid4()


def _msg(msg_id=1, read_ct=1, **overrides):
    message = {"tenant_id": str(TENANT), "decision_id": str(DECISION_ID)}
    message.update(overrides)
    return {"msg_id": msg_id, "read_ct": read_ct, "message": message}


class TestSuccessfulProcessing:
    async def test_processes_and_deletes_message(self):
        client = MagicMock()
        client.delete = AsyncMock()
        pool = object()

        with patch(
            "queues.workers.embedding_worker.process_embedding_job", AsyncMock()
        ) as process_mock:
            await _handle_message(client, pool, _msg())

        process_mock.assert_awaited_once()
        client.delete.assert_awaited_once_with(QueueName.EMBEDDING, 1)


class TestInvalidPayload:
    async def test_malformed_payload_is_left_in_queue(self):
        client = MagicMock()
        client.delete = AsyncMock()
        pool = object()

        with patch("queues.workers.embedding_worker.process_embedding_job", AsyncMock()) as process_mock:
            await _handle_message(client, pool, _msg(message={"decision_id": str(DECISION_ID)}))

        process_mock.assert_not_awaited()
        client.delete.assert_not_awaited()


class TestNonRetryableFailure:
    async def test_decision_not_found_is_non_retryable_and_not_deleted(self):
        client = MagicMock()
        client.delete = AsyncMock()
        pool = object()

        with patch(
            "queues.workers.embedding_worker.process_embedding_job",
            AsyncMock(side_effect=DecisionNotFoundError("gone")),
        ):
            await _handle_message(client, pool, _msg())

        client.delete.assert_not_awaited()

    async def test_validation_error_is_non_retryable_and_not_deleted(self):
        client = MagicMock()
        client.delete = AsyncMock()
        pool = object()

        with patch(
            "queues.workers.embedding_worker.process_embedding_job",
            AsyncMock(side_effect=ValidationError.from_exception_data("EmbeddingJob", [])),
        ):
            await _handle_message(client, pool, _msg())

        client.delete.assert_not_awaited()


class TestRetryableFailure:
    async def test_unexpected_error_leaves_message_for_retry(self):
        client = MagicMock()
        client.delete = AsyncMock()
        pool = object()

        with patch(
            "queues.workers.embedding_worker.process_embedding_job",
            AsyncMock(side_effect=RuntimeError("transient DB error")),
        ):
            await _handle_message(client, pool, _msg())

        client.delete.assert_not_awaited()
