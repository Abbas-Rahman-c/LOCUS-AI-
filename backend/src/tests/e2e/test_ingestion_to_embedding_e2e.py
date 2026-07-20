"""
End-to-end mock test: one pgmq ingestion message all the way through to a
persisted decision_embeddings row.

Exercises the REAL glue code across every module in the chain:

    queues.workers.event_worker._handle_message()
    -> modules.ingestion.dedup.ledger (is_duplicate/mark_seen)
    -> modules.ingestion.raw_events.store.store_raw_event()
    -> modules.ai.pipeline.service.process_and_persist_event()
        -> modules.ai.pipeline.orchestrator.process_ai_event()
            -> modules.ai.triage.classifier.classify()      [Claude - mocked]
            -> modules.ai.extraction.extractor.extract()    [Claude - mocked]
        -> modules.decisions.pipeline_persistence.persist_decision_from_extraction()
        -> queues.pgmq.producer.enqueue_embedding_job()
    -> queues.workers.embedding_worker._handle_message()
        -> modules.ai.embeddings.service.process_embedding_job()
            -> modules.ai.embeddings.provider.embed_document()  [Voyage - mocked]

Only three things are ever mocked: the Anthropic client (classify/extract),
voyageai.Embedding.acreate (embed_document), and the database (one shared
fake asyncpg pool/connection - no real Postgres connection is made). Every
other function in the chain runs for real. No live external API call is
made anywhere in this test.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.ai.extraction.schemas import ActorRole, DecisionStatus, RecordType
from modules.ai.triage.schemas import TriageDecision, TriageReasonCode
from queues.pgmq.queues import QueueName
from queues.workers.embedding_worker import _handle_message as handle_embedding_message
from queues.workers.event_worker import _handle_message as handle_event_message

pytestmark = pytest.mark.asyncio

TENANT = uuid.uuid4()
CONNECTION_ID = uuid.uuid4()
RAW_EVENT_ID = uuid.uuid4()
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
    """One shared fake connection driving every DB call in the chain.

    fetchrow_queue and fetchval_queue are each consumed in call order -
    every call site across dedup/raw_events/persistence/embeddings is
    scripted explicitly below so the test fails loudly (IndexError) if the
    real code path ever calls the database a different number of times
    than expected, rather than silently returning None everywhere.
    """

    def __init__(self, fetchrow_queue, fetchval_queue):
        self._fetchrow_queue = list(fetchrow_queue)
        self._fetchval_queue = list(fetchval_queue)
        self.execute_calls: list[tuple] = []

    def transaction(self):
        return _FakeTransaction()

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        return "INSERT 0 1"

    async def fetchrow(self, query, *args):
        row = self._fetchrow_queue.pop(0)
        return _FakeRecord(row) if row is not None else None

    async def fetchval(self, query, *args):
        return self._fetchval_queue.pop(0)


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


def _envelope_payload() -> dict:
    return {
        "tenant_id": str(TENANT),
        "source": "gmail",
        "source_id": "18d1234abcd",
        "actor": "alice@example.com",
        "permission_scope": [],
        "raw_content": {"subject": "Re: pricing", "body": "We decided to ship Friday."},
    }


def _fake_triage_message():
    return SimpleNamespace(content=[
        SimpleNamespace(
            type="tool_use",
            name="record_triage_result",
            input={
                "decision": TriageDecision.KEEP.value,
                "confidence": 0.95,
                "reason_code": TriageReasonCode.EXPLICIT_DECISION.value,
            },
        )
    ])


def _fake_extraction_message():
    return SimpleNamespace(content=[
        SimpleNamespace(
            type="tool_use",
            name="record_extraction_result",
            input={
                "record_type": RecordType.DECISION.value,
                "status": DecisionStatus.DECIDED.value,
                "decision_statement": "Ship the new pricing page on Friday.",
                "rationale": "Marketing needs it live before the campaign.",
                "alternatives_considered": [],
                "actors": [{"source_actor_id": "alice@example.com", "role": ActorRole.DECIDED_BY.value}],
                "confidence": 0.92,
            },
        )
    ])


def _fake_discard_triage_message():
    return SimpleNamespace(content=[
        SimpleNamespace(
            type="tool_use",
            name="record_triage_result",
            input={
                "decision": TriageDecision.DISCARD.value,
                "confidence": 0.9,
                "reason_code": TriageReasonCode.SOCIAL_CHATTER.value,
            },
        )
    ])


def _mock_anthropic_client():
    client = MagicMock()
    client.beta.tools.messages.create = AsyncMock(
        side_effect=[_fake_triage_message(), _fake_extraction_message()]
    )
    return client


def _mock_discard_anthropic_client():
    """Triage-only client: extraction must never be called for a DISCARD event."""
    client = MagicMock()
    client.beta.tools.messages.create = AsyncMock(return_value=_fake_discard_triage_message())
    return client


class TestFullIngestionToEmbeddingChain:
    async def test_keep_event_produces_a_decision_and_an_embedding(self, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "test-voyage-key")
        monkeypatch.setenv("VOYAGE_MODEL", "voyage-4")
        monkeypatch.delenv("VOYAGE_OUTPUT_DIMENSION", raising=False)
        import common.config.voyage_config as voyage_config_module

        voyage_config_module._settings = None

        conn = _FakeConnection(
            fetchrow_queue=[
                {"id": CONNECTION_ID},                                  # raw_events: resolve connection_id
                {"id": RAW_EVENT_ID},                                    # raw_events: INSERT ... RETURNING id
                None,                                                    # pipeline_persistence: no existing decision
                {"id": DECISION_ID, "tenant_id": TENANT},                 # pipeline_persistence: INSERT decisions
                {"id": uuid.uuid4()},                                     # pipeline_persistence: actor upsert (email)
                {                                                         # embedding_service: SELECT decision
                    "tenant_id": TENANT,
                    "decision_statement": "Ship the new pricing page on Friday.",
                    "rationale": "Marketing needs it live before the campaign.",
                    "alternatives_considered": [],
                },
            ],
            fetchval_queue=[False],  # is_duplicate: not a duplicate
        )
        pool = _FakePool(conn)

        pgmq_client = MagicMock()
        pgmq_client.delete = AsyncMock()
        sent_embedding_jobs: list[dict] = []

        async def fake_send(queue, message):
            if queue == QueueName.EMBEDDING:
                sent_embedding_jobs.append(message)
            return 1

        pgmq_client.send = AsyncMock(side_effect=fake_send)

        mock_client = _mock_anthropic_client()
        with (
            patch("database.tenant_context.get_db_pool", return_value=pool),
            patch("modules.ai.triage.classifier.get_anthropic_client", return_value=mock_client),
            patch("modules.ai.extraction.extractor.get_anthropic_client", return_value=mock_client),
            patch("queues.pgmq.producer.get_pgmq_client", return_value=pgmq_client),
        ):
            # 1. Ingestion side: pgmq message -> dedup -> AI pipeline -> persist -> enqueue
            event_msg = {"msg_id": 100, "message": _envelope_payload()}
            await handle_event_message(pgmq_client, pool, event_msg)

        # The ingestion message was fully processed and deleted.
        pgmq_client.delete.assert_awaited_once_with(QueueName.INGESTION, 100)
        assert len(sent_embedding_jobs) == 1
        assert sent_embedding_jobs[0]["decision_id"] == str(DECISION_ID)
        assert sent_embedding_jobs[0]["tenant_id"] == str(TENANT)

        # Exactly the embedding-service fetch remains unconsumed at this
        # point - proves the ingestion side made exactly the DB calls this
        # test scripted (connection resolve, raw_events insert, existing-
        # decision check, decision insert, actor upsert), no more, no fewer.
        assert conn._fetchrow_queue == [
            {
                "tenant_id": TENANT,
                "decision_statement": "Ship the new pricing page on Friday.",
                "rationale": "Marketing needs it live before the campaign.",
                "alternatives_considered": [],
            }
        ]

        with patch(
            "voyageai.Embedding.acreate",
            AsyncMock(return_value=SimpleNamespace(data=[SimpleNamespace(embedding=EMBEDDING)])),
        ):
            # 2. Embedding side: the job pgmq now "holds" is read and processed.
            embedding_msg = {"msg_id": 200, "message": sent_embedding_jobs[0]}
            await handle_embedding_message(pgmq_client, pool, embedding_msg)

        assert pgmq_client.delete.await_count == 2
        pgmq_client.delete.assert_awaited_with(QueueName.EMBEDDING, 200)

        # A real embedding upsert ran against decision_embeddings.
        embedding_upserts = [c for c in conn.execute_calls if "decision_embeddings" in c[0]]
        assert len(embedding_upserts) == 1
        upsert_args = embedding_upserts[0][1]
        assert upsert_args[0] == DECISION_ID
        assert upsert_args[1] == TENANT

        # Every fetchrow/fetchval response was actually consumed - proves
        # the real code made exactly the DB calls this test scripted, no
        # more and no fewer.
        assert conn._fetchrow_queue == []
        assert conn._fetchval_queue == []


class TestDiscardNeverCreatesADecisionOrEmbeddingJob:
    async def test_discard_event_is_deleted_with_no_decision_or_embedding_job(self):
        conn = _FakeConnection(
            fetchrow_queue=[
                {"id": CONNECTION_ID},   # raw_events: resolve connection_id
                {"id": RAW_EVENT_ID},     # raw_events: INSERT ... RETURNING id
                # No further fetchrow calls: DISCARD skips extraction,
                # persistence, and embedding enqueue entirely.
            ],
            fetchval_queue=[False],  # is_duplicate: not a duplicate
        )
        pool = _FakePool(conn)

        pgmq_client = MagicMock()
        pgmq_client.delete = AsyncMock()
        pgmq_client.send = AsyncMock()

        with (
            patch("database.tenant_context.get_db_pool", return_value=pool),
            patch(
                "modules.ai.triage.classifier.get_anthropic_client",
                return_value=_mock_discard_anthropic_client(),
            ),
            patch("modules.ai.extraction.extractor.get_anthropic_client") as extract_client_patch,
        ):
            event_msg = {"msg_id": 101, "message": _envelope_payload()}
            await handle_event_message(pgmq_client, pool, event_msg)

        # Extraction's Anthropic client was never even fetched - proves
        # extract() was never called for a DISCARD event.
        extract_client_patch.assert_not_called()
        # No embedding job was ever enqueued.
        pgmq_client.send.assert_not_awaited()
        # The message is still deleted - DISCARD is a successful, terminal
        # outcome, not a failure.
        pgmq_client.delete.assert_awaited_once_with(QueueName.INGESTION, 101)
        # No decision-insert or actor-insert fetchrow calls were made.
        assert conn._fetchrow_queue == []
        assert conn._fetchval_queue == []


class TestDuplicateEventNeverReachesTheAIPipeline:
    async def test_duplicate_event_is_deleted_without_calling_claude_or_voyage(self):
        conn = _FakeConnection(fetchrow_queue=[], fetchval_queue=[True])  # is_duplicate: True
        pool = _FakePool(conn)

        pgmq_client = MagicMock()
        pgmq_client.delete = AsyncMock()
        pgmq_client.send = AsyncMock()

        with (
            patch("database.tenant_context.get_db_pool", return_value=pool),
            patch("modules.ai.triage.classifier.get_anthropic_client") as triage_client_patch,
            patch("modules.ai.extraction.extractor.get_anthropic_client") as extract_client_patch,
        ):
            event_msg = {"msg_id": 102, "message": _envelope_payload()}
            await handle_event_message(pgmq_client, pool, event_msg)

        triage_client_patch.assert_not_called()
        extract_client_patch.assert_not_called()
        pgmq_client.send.assert_not_awaited()
        pgmq_client.delete.assert_awaited_once_with(QueueName.INGESTION, 102)
        assert conn._fetchval_queue == []
