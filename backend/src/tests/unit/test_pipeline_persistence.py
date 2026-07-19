"""
Unit tests for modules.decisions.pipeline_persistence.persist_decision_from_extraction().

Uses the real tenant_conn() against a fake pool/connection (same pattern as
test_vector_repository.py) - no real Postgres connection is made. fetchrow
responses are scripted in call order via a queue so the existing-decision
check, the decision insert, and any actor-resolution lookups can each
return a different canned row.
"""
from __future__ import annotations

import uuid

import asyncpg
import pytest

from modules.ai.extraction.schemas import ActorReference, ActorRole, DecisionStatus, ExtractionResult, RecordType
from modules.decisions.pipeline_persistence import (
    ActorResolutionError,
    DecisionPersistenceError,
    UnsupportedActorSourceError,
    persist_decision_from_extraction,
)
from modules.ingestion.envelope.schemas import EventEnvelope

pytestmark = pytest.mark.asyncio

TENANT = uuid.uuid4()
RAW_EVENT_ID = uuid.uuid4()
DECISION_ID = uuid.uuid4()
ACTOR_ID = uuid.uuid4()


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeRecord(dict):
    """dict subclass so both row["field"] and dict(row) work, like asyncpg.Record."""


class _FakeConnection:
    """fetchrow_queue / execute_error let each test script exact responses."""

    def __init__(self, fetchrow_queue: list[dict | None] | None = None):
        self._fetchrow_queue = list(fetchrow_queue or [])
        self.fetchrow_calls: list[tuple] = []
        self.execute_calls: list[tuple] = []
        self.execute_error: Exception | None = None
        self.fetchrow_error: Exception | None = None

    def transaction(self):
        return _FakeTransaction()

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        if self.execute_error is not None:
            raise self.execute_error
        return "INSERT 0 1"

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        if self.fetchrow_error is not None:
            raise self.fetchrow_error
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


def _event(**overrides) -> EventEnvelope:
    base = dict(
        tenant_id=TENANT,
        source="gmail",
        source_id="18d1234abcd",
        actor="alice@example.com",
        permission_scope=[],
        raw_content={"subject": "Re: pricing", "body": "We decided to ship Friday."},
    )
    base.update(overrides)
    return EventEnvelope(**base)


def _extraction(**overrides) -> ExtractionResult:
    base = dict(
        record_type=RecordType.DECISION,
        status=DecisionStatus.DECIDED,
        decision_statement="Ship Friday.",
        rationale=None,
        alternatives_considered=[],
        actors=[],
        confidence=0.9,
    )
    base.update(overrides)
    return ExtractionResult(**base)


def _decision_row(tenant_id=TENANT, decision_id=DECISION_ID):
    return {"id": decision_id, "tenant_id": tenant_id}


class TestNewDecisionPersistence:
    async def test_persists_new_decision_and_returns_id(self):
        conn = _FakeConnection(fetchrow_queue=[None, _decision_row()])
        pool = _FakePool(conn)

        decision_id = await persist_decision_from_extraction(
            pool, TENANT, _event(), _extraction(), RAW_EVENT_ID
        )

        assert decision_id == DECISION_ID
        insert_call = conn.fetchrow_calls[1]
        assert "INSERT INTO decisions" in insert_call[0]
        args = insert_call[1]
        assert args[0] == TENANT
        assert args[-1] == RAW_EVENT_ID  # origin_raw_event_id is the last bound param

    async def test_empty_permission_scope_is_passed_through_unchanged(self):
        """Empty permission_scope must remain empty (workspace-wide) - never
        substituted with a default that would change that meaning."""
        conn = _FakeConnection(fetchrow_queue=[None, _decision_row()])
        pool = _FakePool(conn)

        await persist_decision_from_extraction(
            pool, TENANT, _event(permission_scope=[]), _extraction(), RAW_EVENT_ID
        )

        args = conn.fetchrow_calls[1][1]
        assert args[9] == []  # permission_scope bound param

    async def test_confidence_and_scope_are_carried_through(self):
        conn = _FakeConnection(fetchrow_queue=[None, _decision_row()])
        pool = _FakePool(conn)

        await persist_decision_from_extraction(
            pool, TENANT, _event(), _extraction(confidence=0.42), RAW_EVENT_ID, scope="user"
        )

        args = conn.fetchrow_calls[1][1]
        assert args[6] == "user"    # scope
        assert args[8] == 0.42      # confidence


class TestSourcePersistence:
    async def test_permalink_creates_a_decision_sources_row(self):
        conn = _FakeConnection(fetchrow_queue=[None, _decision_row()])
        pool = _FakePool(conn)

        await persist_decision_from_extraction(
            pool, TENANT, _event(), _extraction(), RAW_EVENT_ID,
            source_permalink="https://mail.google.com/mail/u/0/#inbox/18d1234abcd",
        )

        source_inserts = [c for c in conn.execute_calls if "decision_sources" in c[0]]
        assert len(source_inserts) == 1
        assert source_inserts[0][1][3] == "https://mail.google.com/mail/u/0/#inbox/18d1234abcd"
        assert source_inserts[0][1][2] == RAW_EVENT_ID

    async def test_no_permalink_skips_decision_sources_entirely(self):
        """decision_sources.permalink is NOT NULL - never insert a fabricated one."""
        conn = _FakeConnection(fetchrow_queue=[None, _decision_row()])
        pool = _FakePool(conn)

        await persist_decision_from_extraction(
            pool, TENANT, _event(), _extraction(), RAW_EVENT_ID, source_permalink=None
        )

        source_inserts = [c for c in conn.execute_calls if "decision_sources" in c[0]]
        assert source_inserts == []


class TestActorPersistence:
    async def test_resolves_and_persists_gmail_actor_by_email(self):
        conn = _FakeConnection(fetchrow_queue=[
            None,                               # no existing decision
            _decision_row(),                     # decision insert
            {"id": ACTOR_ID},                     # actor upsert (email path)
        ])
        pool = _FakePool(conn)
        extraction = _extraction(
            actors=[ActorReference(source_actor_id="alice@example.com", role=ActorRole.DECIDED_BY)]
        )

        await persist_decision_from_extraction(
            pool, TENANT, _event(source="gmail"), extraction, RAW_EVENT_ID
        )

        actor_inserts = [c for c in conn.execute_calls if "decision_actors" in c[0]]
        assert len(actor_inserts) == 1
        assert actor_inserts[0][1] == (TENANT, DECISION_ID, ACTOR_ID, "decided_by")

    async def test_resolves_slack_actor_via_select_then_insert(self):
        conn = _FakeConnection(fetchrow_queue=[
            None,                 # no existing decision
            _decision_row(),      # decision insert
            None,                 # actor SELECT: not found
            {"id": ACTOR_ID},      # actor INSERT
        ])
        pool = _FakePool(conn)
        extraction = _extraction(
            actors=[ActorReference(source_actor_id="U0BGBSV33NG", role=ActorRole.MENTIONED)]
        )

        await persist_decision_from_extraction(
            pool, TENANT, _event(source="slack", actor="U0BGBSV33NG"), extraction, RAW_EVENT_ID
        )

        actor_inserts = [c for c in conn.execute_calls if "decision_actors" in c[0]]
        assert actor_inserts[0][1] == (TENANT, DECISION_ID, ACTOR_ID, "mentioned")

    async def test_unsupported_source_raises_before_any_actor_insert(self):
        conn = _FakeConnection(fetchrow_queue=[None, _decision_row()])
        pool = _FakePool(conn)
        extraction = _extraction(
            actors=[ActorReference(source_actor_id="x", role=ActorRole.MENTIONED)]
        )

        with pytest.raises(UnsupportedActorSourceError):
            await persist_decision_from_extraction(
                pool, TENANT, _event(source="carrier_pigeon"), extraction, RAW_EVENT_ID
            )


class TestIdempotency:
    async def test_existing_decision_for_raw_event_is_returned_without_reinserting(self):
        conn = _FakeConnection(fetchrow_queue=[_decision_row(decision_id=DECISION_ID)])
        pool = _FakePool(conn)

        decision_id = await persist_decision_from_extraction(
            pool, TENANT, _event(), _extraction(), RAW_EVENT_ID
        )

        assert decision_id == DECISION_ID
        # Only the existing-decision check ran - no INSERT INTO decisions.
        assert len(conn.fetchrow_calls) == 1
        decision_inserts = [c for c in conn.execute_calls if "INSERT INTO decisions" in c[0]]
        assert decision_inserts == []


class TestFailureHandling:
    async def test_database_error_during_insert_raises_persistence_error(self):
        conn = _FakeConnection(fetchrow_queue=[None])
        conn.fetchrow_error = None
        pool = _FakePool(conn)

        # Force the second fetchrow (decision insert) to fail.
        original_fetchrow = conn.fetchrow
        call_count = {"n": 0}

        async def flaky_fetchrow(query, *args):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise asyncpg.PostgresError("connection reset")
            return await original_fetchrow(query, *args)

        conn.fetchrow = flaky_fetchrow

        with pytest.raises(DecisionPersistenceError):
            await persist_decision_from_extraction(
                pool, TENANT, _event(), _extraction(), RAW_EVENT_ID
            )

    async def test_actor_resolution_database_error_raises_actor_resolution_error(self):
        conn = _FakeConnection(fetchrow_queue=[None, _decision_row()])
        conn.fetchrow_calls_seen = 0
        pool = _FakePool(conn)

        original_fetchrow = conn.fetchrow
        call_count = {"n": 0}

        async def flaky_fetchrow(query, *args):
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise asyncpg.PostgresError("connection reset")
            return await original_fetchrow(query, *args)

        conn.fetchrow = flaky_fetchrow
        extraction = _extraction(
            actors=[ActorReference(source_actor_id="alice@example.com", role=ActorRole.DECIDED_BY)]
        )

        with pytest.raises(ActorResolutionError):
            await persist_decision_from_extraction(
                pool, TENANT, _event(), extraction, RAW_EVENT_ID
            )
