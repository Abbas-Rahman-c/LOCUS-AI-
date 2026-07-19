"""
Unit tests for queues.pgmq.client.PgmqClient.

asyncpg is mocked completely - no real database connection is made.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from queues.pgmq.client import PgmqClient
from queues.pgmq.queues import QueueName

pytestmark = pytest.mark.asyncio


def _fake_pool(fetchrow_return=None, fetch_return=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.execute = AsyncMock(return_value="OK")

    class _AcquireCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *_):
            return False

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCtx())
    pool._conn = conn
    return pool


class TestSend:
    async def test_message_dict_is_json_serialized_before_binding(self):
        """asyncpg has no dict -> jsonb codec: binding a raw dict fails
        client-side. send() must json.dumps() the message first."""
        pool = _fake_pool(fetchrow_return=[42])
        client = PgmqClient(pool)

        await client.send(QueueName.INGESTION, {"tenant_id": "abc", "source": "gmail"})

        call_args = pool._conn.fetchrow.call_args[0]
        bound_message = call_args[2]
        assert isinstance(bound_message, str)
        assert json.loads(bound_message) == {"tenant_id": "abc", "source": "gmail"}

    async def test_returns_message_id(self):
        pool = _fake_pool(fetchrow_return=[7])
        client = PgmqClient(pool)
        msg_id = await client.send(QueueName.EMBEDDING, {"a": 1})
        assert msg_id == 7


class TestRead:
    async def test_returns_list_of_dicts(self):
        pool = _fake_pool(fetch_return=[{"msg_id": 1, "message": {"a": 1}}])
        client = PgmqClient(pool)
        result = await client.read(QueueName.INGESTION, vt=30, batch=5)
        assert result == [{"msg_id": 1, "message": {"a": 1}}]


class TestDelete:
    async def test_calls_pgmq_delete_with_bigint_cast(self):
        pool = _fake_pool()
        client = PgmqClient(pool)
        await client.delete(QueueName.INGESTION, 123)
        call_args = pool._conn.execute.call_args[0]
        assert "pgmq.delete" in call_args[0]
        assert call_args[1:] == (QueueName.INGESTION.value, 123)
