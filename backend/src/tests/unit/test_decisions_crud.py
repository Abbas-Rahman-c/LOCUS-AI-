"""
Unit tests for the decisions CRUD and supersession operations.

Tests:
  - create_decision: inserts with correct tenant_id, returns full DecisionOut.
  - patch_decision_status: updates status field; LookupError when not found.
  - supersede_decision:
    * Creates new decision.
    * Marks old as status='superseded' with superseded_by = new_id.
    * Returns new DecisionOut.
    * Raises LookupError if old decision does not belong to tenant.
  - Cross-tenant probe blocked: attempting to supersede another tenant's ID raises.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.decisions.schemas import DecisionCreate, StatusUpdate
from modules.decisions import service
from modules.security.tenant_guard import TenantScopeError


# ─── helpers ─────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _make_row(tenant_id: uuid.UUID, decision_id: uuid.UUID | None = None, **overrides) -> dict:
    """Return a dict shaped like a decisions DB row."""
    base = {
        "id": decision_id or uuid.uuid4(),
        "tenant_id": tenant_id,
        "record_type": "decision",
        "decision_statement": "Default statement",
        "rationale": "Default rationale",
        "status": "proposed",
        "superseded_by": None,
        "scope": "team",
        "confidence": 1.0,
        "created_at": _now(),
        "updated_at": _now(),
    }
    base.update(overrides)
    return base


def _dict_to_record(d: dict):
    """Wrap a plain dict so it behaves like an asyncpg Record."""
    record = MagicMock()
    record.__getitem__ = lambda self, key: d[key]
    record.keys = lambda: d.keys()
    record.items = lambda: d.items()
    record.__iter__ = lambda self: iter(d)
    for k, v in d.items():
        setattr(record, k, v)
    return record


def _make_conn(*fetchrow_results, execute_result="UPDATE 1"):
    """
    Build a mock asyncpg connection that yields the given rows in order from fetchrow().
    execute() always succeeds.
    Supports `async with conn.transaction()` context manager.
    """
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=execute_result)

    records = [_dict_to_record(r) if r is not None else None for r in fetchrow_results]
    conn.fetchrow = AsyncMock(side_effect=records)

    # transaction() must work as `async with conn.transaction()`
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    return conn


def _make_pool_with_conn(conn):
    pool = MagicMock()

    class _AcquireCtx:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *_):
            pass

    pool.acquire = MagicMock(return_value=_AcquireCtx())
    return pool


# ─── create_decision ──────────────────────────────────────────────────────────

def test_create_decision_returns_correct_tenant():
    """create_decision must return a DecisionOut with the correct tenant_id."""
    tenant_id = uuid.uuid4()
    decision_id = uuid.uuid4()
    row = _make_row(tenant_id, decision_id, decision_statement="Use PostgreSQL", status="decided")

    conn = _make_conn(row)
    pool = _make_pool_with_conn(conn)

    data = DecisionCreate(
        decision_statement="Use PostgreSQL",
        rationale="Proven reliability",
        status="decided",
    )

    async def run():
        result = await service.create_decision(data, tenant_id, pool)
        assert result.tenant_id == tenant_id
        assert result.id == decision_id
        assert result.decision_statement == "Use PostgreSQL"
        assert result.status == "decided"
        assert result.superseded_by is None

    asyncio.run(run())


def test_create_decision_layer2_blocks_wrong_tenant():
    """If the DB somehow returns a row from the wrong tenant, Layer 2 must block it."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    row = _make_row(tenant_b)   # wrong tenant in DB row!

    conn = _make_conn(row)
    pool = _make_pool_with_conn(conn)

    data = DecisionCreate(decision_statement="Leaked", status="proposed")

    async def run():
        with pytest.raises(TenantScopeError):
            await service.create_decision(data, tenant_a, pool)

    asyncio.run(run())


# ─── patch_decision_status ────────────────────────────────────────────────────

def test_patch_decision_status_updates_status():
    """patch_decision_status must return the decision with the updated status."""
    tenant_id = uuid.uuid4()
    decision_id = uuid.uuid4()
    row = _make_row(tenant_id, decision_id, status="decided")

    conn = _make_conn(row)
    pool = _make_pool_with_conn(conn)

    async def run():
        result = await service.patch_decision_status(decision_id, "decided", tenant_id, pool)
        assert result.status == "decided"
        assert result.tenant_id == tenant_id

    asyncio.run(run())


def test_patch_decision_status_raises_when_not_found():
    """patch_decision_status must raise LookupError when the decision doesn't exist."""
    tenant_id = uuid.uuid4()
    decision_id = uuid.uuid4()

    conn = _make_conn(None)   # DB returns nothing
    pool = _make_pool_with_conn(conn)

    async def run():
        with pytest.raises(LookupError):
            await service.patch_decision_status(decision_id, "decided", tenant_id, pool)

    asyncio.run(run())


# ─── supersede_decision ───────────────────────────────────────────────────────

def test_supersede_decision_returns_new_decision():
    """supersede_decision must return the newly created decision."""
    tenant_id = uuid.uuid4()
    old_id = uuid.uuid4()
    new_id = uuid.uuid4()

    # conn.fetchrow called twice: once for FOR UPDATE, once for INSERT RETURNING
    old_row = _make_row(tenant_id, old_id, status="decided")
    new_row = _make_row(tenant_id, new_id, decision_statement="New policy", status="proposed")

    conn = _make_conn(old_row, new_row)
    pool = _make_pool_with_conn(conn)

    new_data = DecisionCreate(
        decision_statement="New policy",
        rationale="Better approach found",
        status="proposed",
    )

    async def run():
        result = await service.supersede_decision(old_id, new_data, tenant_id, pool)
        assert result.id == new_id
        assert result.decision_statement == "New policy"
        assert result.tenant_id == tenant_id

    asyncio.run(run())


def test_supersede_decision_marks_old_as_superseded():
    """supersede_decision must call execute() to set status='superseded' on the old record."""
    tenant_id = uuid.uuid4()
    old_id = uuid.uuid4()
    new_id = uuid.uuid4()

    old_row = _make_row(tenant_id, old_id, status="decided")
    new_row = _make_row(tenant_id, new_id, decision_statement="Replacement", status="proposed")

    conn = _make_conn(old_row, new_row)
    pool = _make_pool_with_conn(conn)

    new_data = DecisionCreate(decision_statement="Replacement", status="proposed")

    async def run():
        await service.supersede_decision(old_id, new_data, tenant_id, pool)
        # execute() should have been called to UPDATE the old decision
        assert conn.execute.called
        # The UPDATE call should contain 'superseded' in the SQL
        call_args = conn.execute.call_args[0]
        assert "superseded" in call_args[0].lower()
        # The new decision UUID should appear in the call args
        assert new_id in call_args

    asyncio.run(run())


def test_supersede_decision_raises_when_old_not_found():
    """supersede_decision must raise LookupError when the old decision doesn't exist."""
    tenant_id = uuid.uuid4()
    old_id = uuid.uuid4()

    conn = _make_conn(None)   # FOR UPDATE returns nothing
    pool = _make_pool_with_conn(conn)

    new_data = DecisionCreate(decision_statement="Replacement", status="proposed")

    async def run():
        with pytest.raises(LookupError):
            await service.supersede_decision(old_id, new_data, tenant_id, pool)

    asyncio.run(run())


def test_supersede_decision_blocks_cross_tenant_attempt():
    """supersede_decision must block if the old decision belongs to a different tenant (Layer 2)."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    old_id = uuid.uuid4()

    # Simulate DB returning a row belonging to tenant_b when queried as tenant_a
    old_row = _make_row(tenant_b, old_id, status="decided")

    conn = _make_conn(old_row)
    pool = _make_pool_with_conn(conn)

    new_data = DecisionCreate(decision_statement="Cross-tenant attack", status="proposed")

    async def run():
        with pytest.raises(TenantScopeError):
            await service.supersede_decision(old_id, new_data, tenant_a, pool)

    asyncio.run(run())


# ─── relationship integrity ───────────────────────────────────────────────────

def test_superseded_decision_relationship_intact():
    """
    After supersession the old row has superseded_by = new_id.
    This verifies the relationship is queryable independently.
    Simulates fetching the old decision after supersession via get_decision.
    """
    tenant_id = uuid.uuid4()
    old_id = uuid.uuid4()
    new_id = uuid.uuid4()

    # Simulate fetching the old decision *after* it was superseded
    old_after = _make_row(
        tenant_id, old_id,
        status="superseded",
        superseded_by=new_id,
    )

    conn = _make_conn(old_after)
    pool = _make_pool_with_conn(conn)

    async def run():
        result = await service.get_decision(old_id, tenant_id, pool)
        assert result.status == "superseded"
        assert result.superseded_by == new_id

    asyncio.run(run())
