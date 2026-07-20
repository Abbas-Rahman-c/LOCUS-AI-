"""
Unit tests for database.tenant_connection.tenant_conn()'s transaction scope.

Proves the fix described in the module's own docstring: set_config(...,
is_local=true) must run inside an explicitly-opened transaction, or the
setting reverts before the caller's next (separate, implicitly-transacted)
query ever runs. A fake pool/connection/transaction records call order so
these tests assert on ordering directly, without needing a real Postgres
connection.
"""
from __future__ import annotations

import uuid

import pytest

from database.tenant_connection import tenant_conn


class _FakeTransaction:
    def __init__(self, recorder: list, fail_on_exit: bool = False):
        self._recorder = recorder

    async def __aenter__(self):
        self._recorder.append("transaction.start")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self._recorder.append("transaction.rollback")
        else:
            self._recorder.append("transaction.commit")
        return False  # never suppress exceptions


class _FakeConnection:
    def __init__(self, recorder: list):
        self._recorder = recorder

    def transaction(self):
        return _FakeTransaction(self._recorder)

    async def execute(self, query: str, *args):
        self._recorder.append(("execute", query, args))
        return "SET"

    async def fetch(self, query: str, *args):
        self._recorder.append(("fetch", query, args))
        return []


class _FakeAcquireCtx:
    def __init__(self, recorder: list, conn: _FakeConnection):
        self._recorder = recorder
        self._conn = conn

    async def __aenter__(self):
        self._recorder.append("pool.acquire")
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        self._recorder.append("pool.release")
        return False


class _FakePool:
    def __init__(self, recorder: list, conn: _FakeConnection):
        self._recorder = recorder
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._recorder, self._conn)


def _wired_pool() -> tuple[list, _FakePool, _FakeConnection]:
    recorder: list = []
    conn = _FakeConnection(recorder)
    pool = _FakePool(recorder, conn)
    return recorder, pool, conn


def _first_index(recorder: list, predicate) -> int:
    return next(i for i, item in enumerate(recorder) if predicate(item))


class TestTransactionOpensBeforeSetConfig:
    pytestmark = pytest.mark.asyncio

    async def test_transaction_starts_before_set_config_executes(self):
        recorder, pool, _conn = _wired_pool()

        async with tenant_conn(pool, uuid.uuid4()):
            pass

        start_idx = recorder.index("transaction.start")
        execute_idx = _first_index(
            recorder, lambda item: isinstance(item, tuple) and item[0] == "execute"
        )
        assert start_idx < execute_idx

    async def test_set_config_call_targets_app_current_tenant_id(self):
        recorder, pool, _conn = _wired_pool()
        tenant_id = uuid.uuid4()

        async with tenant_conn(pool, tenant_id):
            pass

        _, query, args = next(
            item for item in recorder if isinstance(item, tuple) and item[0] == "execute"
        )
        assert "set_config" in query
        assert "app.current_tenant_id" in query
        assert args[0] == str(tenant_id)


class TestQueriesRunInsideTheOpenTransaction:
    pytestmark = pytest.mark.asyncio

    async def test_caller_queries_execute_before_transaction_commits(self):
        recorder, pool, _conn = _wired_pool()

        async with tenant_conn(pool, uuid.uuid4()) as conn:
            await conn.fetch("SELECT * FROM decisions")

        fetch_idx = _first_index(
            recorder, lambda item: isinstance(item, tuple) and item[0] == "fetch"
        )
        commit_idx = recorder.index("transaction.commit")
        assert fetch_idx < commit_idx

    async def test_multiple_caller_queries_all_run_before_commit(self):
        recorder, pool, _conn = _wired_pool()

        async with tenant_conn(pool, uuid.uuid4()) as conn:
            await conn.fetch("SELECT 1")
            await conn.fetch("SELECT 2")

        commit_idx = recorder.index("transaction.commit")
        fetch_indices = [
            i for i, item in enumerate(recorder) if isinstance(item, tuple) and item[0] == "fetch"
        ]
        assert len(fetch_indices) == 2
        assert all(i < commit_idx for i in fetch_indices)


class TestConnectionReleasedAfterward:
    pytestmark = pytest.mark.asyncio

    async def test_connection_released_after_clean_exit(self):
        recorder, pool, _conn = _wired_pool()

        async with tenant_conn(pool, uuid.uuid4()):
            pass

        assert "pool.release" in recorder
        assert recorder.index("pool.release") > recorder.index("pool.acquire")

    async def test_release_happens_after_transaction_commits(self):
        recorder, pool, _conn = _wired_pool()

        async with tenant_conn(pool, uuid.uuid4()):
            pass

        assert recorder.index("transaction.commit") < recorder.index("pool.release")


class TestExceptionsRollBackAndRelease:
    pytestmark = pytest.mark.asyncio

    async def test_exception_inside_context_rolls_back(self):
        recorder, pool, _conn = _wired_pool()

        with pytest.raises(RuntimeError):
            async with tenant_conn(pool, uuid.uuid4()):
                raise RuntimeError("boom")

        assert "transaction.rollback" in recorder
        assert "transaction.commit" not in recorder

    async def test_exception_inside_context_still_releases_connection(self):
        recorder, pool, _conn = _wired_pool()

        with pytest.raises(RuntimeError):
            async with tenant_conn(pool, uuid.uuid4()):
                raise RuntimeError("boom")

        assert "pool.release" in recorder

    async def test_original_exception_propagates_unchanged(self):
        recorder, pool, _conn = _wired_pool()

        class _Marker(Exception):
            pass

        with pytest.raises(_Marker):
            async with tenant_conn(pool, uuid.uuid4()):
                raise _Marker("distinct exception type must survive")
