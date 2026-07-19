"""
Unit tests for modules.ai.embeddings.service.process_embedding_job().

Uses the real tenant_conn() against a fake pool/connection (same pattern as
test_pipeline_persistence.py / test_vector_repository.py) - no real
Postgres connection is made. embed_document() and get_voyage_config() are
mocked - no real Voyage API call is made.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

from modules.ai.embeddings.service import (
    DecisionNotFoundError,
    EmbeddingPersistenceError,
    process_embedding_job,
)
from queues.pgmq.schemas import EmbeddingJob

pytestmark = pytest.mark.asyncio

TENANT = uuid.uuid4()
DECISION_ID = uuid.uuid4()
EMBEDDING = [0.01 * i for i in range(1024)]


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeRecord(dict):
    pass


class _FakeConnection:
    def __init__(self, fetchrow_queue: list[dict | None] | None = None, execute_error=None):
        self._fetchrow_queue = list(fetchrow_queue or [])
        self.execute_calls: list[tuple] = []
        self.execute_error = execute_error

    def transaction(self):
        return _FakeTransaction()

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        if self.execute_error is not None and "decision_embeddings" in query:
            raise self.execute_error
        return "INSERT 0 1"

    async def fetchrow(self, query, *args):
        if not self._fetchrow_queue:
            return None
        row = self._fetchrow_queue.pop(0)
        return _FakeRecord(row) if row is not None else None


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


def _decision_row(**overrides):
    base = {
        "tenant_id": TENANT,
        "decision_statement": "We chose Stripe for billing.",
        "rationale": "Self-service billing support.",
        "alternatives_considered": ["Paddle"],
    }
    base.update(overrides)
    return base


def _voyage_config():
    return SimpleNamespace(voyage_model="voyage-4", voyage_output_dimension=1024)


class TestSuccessfulEmbedding:
    async def test_fetches_embeds_and_upserts(self):
        conn = _FakeConnection(fetchrow_queue=[_decision_row()])
        pool = _FakePool(conn)
        job = EmbeddingJob(tenant_id=TENANT, decision_id=DECISION_ID)

        with (
            patch("modules.ai.embeddings.service.embed_document", AsyncMock(return_value=EMBEDDING)),
            patch("modules.ai.embeddings.service.get_voyage_config", return_value=_voyage_config()),
        ):
            await process_embedding_job(pool, job)

        upsert_calls = [c for c in conn.execute_calls if "decision_embeddings" in c[0]]
        assert len(upsert_calls) == 1
        args = upsert_calls[0][1]
        assert args[0] == DECISION_ID
        assert args[1] == TENANT
        assert args[3] == "voyage-4"

    async def test_searchable_text_excludes_raw_content_and_metadata(self):
        """Only decision_statement/rationale/alternatives_considered are
        ever read - the fetch query itself never selects raw_content,
        permission_scope, or actor ids."""
        conn = _FakeConnection(fetchrow_queue=[_decision_row()])
        pool = _FakePool(conn)
        job = EmbeddingJob(tenant_id=TENANT, decision_id=DECISION_ID)
        captured_text = {}

        async def fake_embed_document(text):
            captured_text["value"] = text
            return EMBEDDING

        with (
            patch("modules.ai.embeddings.service.embed_document", fake_embed_document),
            patch("modules.ai.embeddings.service.get_voyage_config", return_value=_voyage_config()),
        ):
            await process_embedding_job(pool, job)

        assert "Decision: We chose Stripe for billing." in captured_text["value"]
        assert "Rationale: Self-service billing support." in captured_text["value"]
        assert "Paddle" in captured_text["value"]


class TestDecisionNotFound:
    async def test_missing_decision_raises_decision_not_found(self):
        conn = _FakeConnection(fetchrow_queue=[None])
        pool = _FakePool(conn)
        job = EmbeddingJob(tenant_id=TENANT, decision_id=DECISION_ID)

        with pytest.raises(DecisionNotFoundError):
            await process_embedding_job(pool, job)


class TestIdempotency:
    async def test_upsert_uses_on_conflict_decision_id(self):
        """Re-processing the same job must never create a duplicate row -
        the upsert clause is the actual idempotency mechanism."""
        conn = _FakeConnection(fetchrow_queue=[_decision_row()])
        pool = _FakePool(conn)
        job = EmbeddingJob(tenant_id=TENANT, decision_id=DECISION_ID)

        with (
            patch("modules.ai.embeddings.service.embed_document", AsyncMock(return_value=EMBEDDING)),
            patch("modules.ai.embeddings.service.get_voyage_config", return_value=_voyage_config()),
        ):
            await process_embedding_job(pool, job)

        upsert_calls = [c for c in conn.execute_calls if "decision_embeddings" in c[0]]
        assert len(upsert_calls) == 1
        assert "ON CONFLICT (decision_id) DO UPDATE" in upsert_calls[0][0]


class TestPersistenceFailure:
    async def test_database_error_on_upsert_raises_persistence_error(self):
        conn = _FakeConnection(
            fetchrow_queue=[_decision_row()],
            execute_error=asyncpg.PostgresError("connection reset"),
        )
        pool = _FakePool(conn)
        job = EmbeddingJob(tenant_id=TENANT, decision_id=DECISION_ID)

        with (
            patch("modules.ai.embeddings.service.embed_document", AsyncMock(return_value=EMBEDDING)),
            patch("modules.ai.embeddings.service.get_voyage_config", return_value=_voyage_config()),
        ):
            with pytest.raises(EmbeddingPersistenceError):
                await process_embedding_job(pool, job)
