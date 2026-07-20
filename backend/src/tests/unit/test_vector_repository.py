"""
Unit tests for modules.retrieval.vector.repository.search_similar_decisions().

Uses the real tenant_conn() (fixed in the prior commit) against a fake
pool/connection, so these tests prove the *code path* opens a transaction
and calls set_config('app.current_tenant_id', ...) before querying - i.e.
that RLS is correctly engaged at the connection level. No real Postgres
connection is made here, so nothing in this file proves the database's RLS
policies themselves actually filter rows - a real two-tenant PostgreSQL
integration test is still needed for that and remains pending (no
disposable project-configured test database is available in this
environment; see the branch's final verification report).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from modules.retrieval.vector.repository import search_similar_decisions
from modules.security.tenant_guard import TenantScopeError

EMBEDDING = [0.001 * i for i in range(1024)]


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeRecord(dict):
    """dict subclass so both row["field"] and dict(row) work, like asyncpg.Record."""


class _FakeConnection:
    def __init__(self, rows: list[dict]):
        self._rows = [_FakeRecord(r) for r in rows]
        self.fetch_calls: list[tuple] = []
        self.execute_calls: list[tuple] = []

    def transaction(self):
        return _FakeTransaction()

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        return "SET"

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        return self._rows


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


def _row(**overrides) -> dict:
    row = {
        "decision_id": uuid.uuid4(),
        "decision_statement": "We chose Stripe for PCI-compliant billing.",
        "similarity_score": 0.87,
        "confidence": Decimal("0.900"),
        "tenant_id": None,  # filled in by caller per-test
        "permission_scope": ["team:billing"],
        "rationale": "Supports self-service billing.",
        "alternatives_considered": ["Paddle"],
        "created_at": None,
        "decision_type": "decision",
        "owner": "Jane Doe",
    }
    row.update(overrides)
    return row


pytestmark = pytest.mark.asyncio


class TestTenantScopedExecution:
    async def test_runs_inside_tenant_conn_not_bare_acquire(self):
        """Proof retrieval opens a transaction and sets the GUC before querying -
        not a bare pool.acquire()."""
        tenant_id = uuid.uuid4()
        conn = _FakeConnection([_row(tenant_id=tenant_id)])
        pool = _FakePool(conn)

        await search_similar_decisions(pool, tenant_id, EMBEDDING, top_k=5)

        assert len(conn.execute_calls) == 1
        set_config_query, set_config_args = conn.execute_calls[0]
        assert "set_config" in set_config_query
        assert "app.current_tenant_id" in set_config_query
        assert set_config_args[0] == str(tenant_id)

    async def test_explicit_tenant_id_predicate_present_in_query(self):
        """Defense-in-depth: WHERE d.tenant_id = $2 must be present, not just RLS."""
        tenant_id = uuid.uuid4()
        conn = _FakeConnection([_row(tenant_id=tenant_id)])
        pool = _FakePool(conn)

        await search_similar_decisions(pool, tenant_id, EMBEDDING, top_k=5)

        query, args = conn.fetch_calls[0]
        assert "WHERE d.tenant_id = $2" in query
        assert "JOIN public.decisions" in query
        assert "<=>" in query
        assert "ORDER BY" in query
        vector_literal, bound_tenant_id, top_k = args
        assert bound_tenant_id == tenant_id
        assert top_k == 5

    async def test_never_queries_without_a_tenant_predicate(self):
        """There is no code path here that omits tenant scoping - retrieval
        never performs a global cross-tenant query and filters afterward."""
        tenant_id = uuid.uuid4()
        conn = _FakeConnection([_row(tenant_id=tenant_id)])
        pool = _FakePool(conn)

        await search_similar_decisions(pool, tenant_id, EMBEDDING, top_k=5)

        query = conn.fetch_calls[0][0]
        assert "tenant_id" in query  # present in SELECT and WHERE, never absent


class TestLayer2FailsClosedIfRlsIsEverMisconfigured:
    """Proves the Python-level Layer 2 re-check only - not database RLS
    itself, which no test in this file can exercise (no real Postgres
    connection is made anywhere here)."""

    async def test_wrong_tenant_row_is_rejected_by_layer_2(self):
        """If a row for a DIFFERENT tenant ever came back (RLS misconfigured
        or bypassed), assert_tenant_scope() must catch it and fail loudly -
        never silently return cross-tenant data."""
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        conn = _FakeConnection([_row(tenant_id=tenant_b)])  # wrong tenant on purpose
        pool = _FakePool(conn)

        with pytest.raises(TenantScopeError):
            await search_similar_decisions(pool, tenant_a, EMBEDDING, top_k=5)

    async def test_matching_tenant_rows_pass_through(self):
        tenant_id = uuid.uuid4()
        conn = _FakeConnection([_row(tenant_id=tenant_id), _row(tenant_id=tenant_id)])
        pool = _FakePool(conn)

        results = await search_similar_decisions(pool, tenant_id, EMBEDDING, top_k=5)

        assert len(results) == 2
        assert all(r.tenant_id == tenant_id for r in results)


class TestResultMapping:
    async def test_maps_all_enriched_fields(self):
        tenant_id = uuid.uuid4()
        row = _row(tenant_id=tenant_id)
        conn = _FakeConnection([row])
        pool = _FakePool(conn)

        results = await search_similar_decisions(pool, tenant_id, EMBEDDING, top_k=5)

        match = results[0]
        assert match.decision_id == row["decision_id"]
        assert match.decision_statement == row["decision_statement"]
        assert match.similarity_score == row["similarity_score"]
        assert match.confidence == float(row["confidence"])
        assert match.permission_scope == row["permission_scope"]
        assert match.rationale == row["rationale"]
        assert match.alternatives_considered == row["alternatives_considered"]
        assert match.decision_type == row["decision_type"]
        assert match.owner == row["owner"]

    async def test_empty_result_set_returns_empty_list(self):
        tenant_id = uuid.uuid4()
        conn = _FakeConnection([])
        pool = _FakePool(conn)

        results = await search_similar_decisions(pool, tenant_id, EMBEDDING, top_k=5)
        assert results == []

    async def test_null_permission_scope_becomes_empty_list(self):
        tenant_id = uuid.uuid4()
        conn = _FakeConnection([_row(tenant_id=tenant_id, permission_scope=None)])
        pool = _FakePool(conn)

        results = await search_similar_decisions(pool, tenant_id, EMBEDDING, top_k=5)
        assert results[0].permission_scope == []


class TestValidation:
    async def test_rejects_top_k_below_one(self):
        pool = _FakePool(_FakeConnection([]))
        with pytest.raises(ValueError):
            await search_similar_decisions(pool, uuid.uuid4(), EMBEDDING, top_k=0)

    async def test_rejects_top_k_above_max(self):
        pool = _FakePool(_FakeConnection([]))
        with pytest.raises(ValueError):
            await search_similar_decisions(pool, uuid.uuid4(), EMBEDDING, top_k=51)

    async def test_rejects_wrong_embedding_dimension(self):
        pool = _FakePool(_FakeConnection([]))
        with pytest.raises(ValueError):
            await search_similar_decisions(pool, uuid.uuid4(), [0.1] * 512, top_k=5)

    async def test_rejects_non_list_embedding(self):
        pool = _FakePool(_FakeConnection([]))
        with pytest.raises(ValueError):
            await search_similar_decisions(pool, uuid.uuid4(), "not-a-list", top_k=5)
