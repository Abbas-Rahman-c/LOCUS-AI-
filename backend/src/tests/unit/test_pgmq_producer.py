"""
Unit tests for queues.pgmq.producer.enqueue_event() / enqueue_embedding_job().

get_pgmq_client() is mocked - no real pgmq call is made.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from queues.pgmq.producer import (
    EmbeddingEnqueueError,
    EventEnqueueError,
    enqueue_embedding_job,
    enqueue_event,
)
from queues.pgmq.queues import QueueName

pytestmark = pytest.mark.asyncio


def _valid_envelope(**overrides) -> dict:
    base = {
        "tenant_id": str(uuid.uuid4()),
        "source": "gmail",
        "source_id": "18d1234abcd",
        "actor": "alice@example.com",
        "permission_scope": [],
        "raw_content": {"subject": "Re: pricing", "body": "We decided to ship Friday."},
    }
    base.update(overrides)
    return base


class TestEnqueueEvent:
    async def test_valid_envelope_is_sent_to_ingestion_queue(self):
        client = AsyncMock()
        client.send = AsyncMock(return_value=42)
        with patch("queues.pgmq.producer.get_pgmq_client", return_value=client):
            msg_id = await enqueue_event(_valid_envelope())
        assert msg_id == 42
        args, _ = client.send.call_args
        assert args[0] == QueueName.INGESTION

    async def test_invalid_envelope_raises_before_sending(self):
        client = AsyncMock()
        client.send = AsyncMock()
        with patch("queues.pgmq.producer.get_pgmq_client", return_value=client):
            with pytest.raises(EventEnqueueError):
                await enqueue_event({"source": "gmail"})  # missing required fields
        client.send.assert_not_awaited()

    async def test_send_failure_is_wrapped(self):
        client = AsyncMock()
        client.send = AsyncMock(side_effect=RuntimeError("connection reset"))
        with patch("queues.pgmq.producer.get_pgmq_client", return_value=client):
            with pytest.raises(EventEnqueueError):
                await enqueue_event(_valid_envelope())


class TestEnqueueEmbeddingJob:
    async def test_valid_job_is_sent_to_embedding_queue(self):
        client = AsyncMock()
        client.send = AsyncMock(return_value=7)
        with patch("queues.pgmq.producer.get_pgmq_client", return_value=client):
            msg_id = await enqueue_embedding_job(tenant_id=uuid.uuid4(), decision_id=uuid.uuid4())
        assert msg_id == 7
        args, _ = client.send.call_args
        assert args[0] == QueueName.EMBEDDING

    async def test_job_payload_carries_only_tenant_and_decision_id(self):
        client = AsyncMock()
        client.send = AsyncMock(return_value=1)
        tenant_id, decision_id = uuid.uuid4(), uuid.uuid4()
        with patch("queues.pgmq.producer.get_pgmq_client", return_value=client):
            await enqueue_embedding_job(tenant_id=tenant_id, decision_id=decision_id)
        _, payload = client.send.call_args[0]
        assert set(payload.keys()) == {"tenant_id", "decision_id"}
        assert payload["tenant_id"] == str(tenant_id)
        assert payload["decision_id"] == str(decision_id)

    async def test_send_failure_is_wrapped(self):
        client = AsyncMock()
        client.send = AsyncMock(side_effect=RuntimeError("connection reset"))
        with patch("queues.pgmq.producer.get_pgmq_client", return_value=client):
            with pytest.raises(EmbeddingEnqueueError):
                await enqueue_embedding_job(tenant_id=uuid.uuid4(), decision_id=uuid.uuid4())
