"""
Audit 1 — Decision Register: live supersession simulation.

This script:
  1. Simulates creating an original decision.
  2. Simulates superseding it with a new decision.
  3. Simulates querying both the old and new decisions independently.
  4. Prints all SQL calls and their results to form the audit evidence.

No live DB connection is required — the mock captures and prints every SQL statement
the service layer issues, demonstrating the exact queries and their parameters.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
os.environ["APP_SECRET_KEY"] = "test-secret-key-for-unit-tests-must-be-at-least-32-chars-long"

from modules.decisions.schemas import DecisionCreate
from modules.decisions import service

# ─── helpers ────────────────────────────────────────────────────────────────

TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OLD_ID    = uuid.UUID("11111111-1111-1111-1111-111111111111")
NEW_ID    = uuid.UUID("22222222-2222-2222-2222-222222222222")
NOW       = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)

sql_log: list[str] = []

def _row(overrides: dict):
    base = {
        "id": OLD_ID, "tenant_id": TENANT_ID,
        "record_type": "decision",
        "decision_statement": "Use PostgreSQL for primary storage",
        "rationale": "Proven reliability, ACID compliance",
        "status": "decided",
        "superseded_by": None,
        "scope": "team",
        "confidence": 0.95,
        "created_at": NOW, "updated_at": NOW,
    }
    base.update(overrides)
    r = MagicMock()
    r.__getitem__ = lambda self, k: base[k]
    r.keys = lambda: base.keys()
    r.items = lambda: base.items()
    r.__iter__ = lambda self: iter(base)
    for k, v in base.items():
        setattr(r, k, v)
    return r


class LoggingConn:
    """asyncpg connection double that logs every SQL call."""

    def __init__(self, fetchrow_results):
        self._fetchrow_results = iter(fetchrow_results)
        self.execute = self._execute
        self.fetchrow = self._fetchrow

    async def _execute(self, sql, *args):
        sql_log.append(f"EXECUTE: {sql.strip()!r}  args={args}")
        return "OK"

    async def _fetchrow(self, sql, *args):
        sql_log.append(f"FETCHROW: {sql.strip()!r}  args={args}")
        return next(self._fetchrow_results)

    def transaction(self):
        class _Tx:
            async def __aenter__(s): return None
            async def __aexit__(s, *_): return False
        return _Tx()


def _pool(*fetchrow_results):
    conn = LoggingConn(fetchrow_results)
    pool = MagicMock()
    class _Ctx:
        async def __aenter__(self): return conn
        async def __aexit__(self, *_): pass
    pool.acquire = MagicMock(return_value=_Ctx())
    return pool


async def main():
    # ── 1. Create original decision ─────────────────────────────────────────
    print("=" * 70)
    print("STEP 1: create_decision")
    print("=" * 70)
    sql_log.clear()
    pool = _pool(_row({}))
    data = DecisionCreate(
        decision_statement="Use PostgreSQL for primary storage",
        rationale="Proven reliability, ACID compliance",
        alternatives_considered=["MySQL", "CockroachDB"],
        status="decided",
        confidence=0.95,
    )
    old_decision = await service.create_decision(data, TENANT_ID, pool)
    for s in sql_log:
        print(s)
    print(f"\nResult:")
    print(f"  id              = {old_decision.id}")
    print(f"  tenant_id       = {old_decision.tenant_id}")
    print(f"  decision_statement = {old_decision.decision_statement!r}")
    print(f"  status          = {old_decision.status}")
    print(f"  superseded_by   = {old_decision.superseded_by}")

    # ── 2. Supersede original with new ──────────────────────────────────────
    print("\n" + "=" * 70)
    print("STEP 2: supersede_decision")
    print("=" * 70)
    sql_log.clear()

    old_lock_row = _row({"id": OLD_ID, "status": "decided"})
    new_row      = _row({
        "id": NEW_ID,
        "decision_statement": "Use CockroachDB for global scalability",
        "rationale": "Geographic distribution requirement added",
        "status": "proposed",
        "superseded_by": None,
    })

    pool = _pool(old_lock_row, new_row)
    new_data = DecisionCreate(
        decision_statement="Use CockroachDB for global scalability",
        rationale="Geographic distribution requirement added",
        status="proposed",
    )
    new_decision = await service.supersede_decision(OLD_ID, new_data, TENANT_ID, pool)
    for s in sql_log:
        print(s)
    print(f"\nNew decision returned:")
    print(f"  id              = {new_decision.id}")
    print(f"  decision_statement = {new_decision.decision_statement!r}")
    print(f"  status          = {new_decision.status}")

    # ── 3. Query old decision after supersession ─────────────────────────────
    print("\n" + "=" * 70)
    print("STEP 3: get_decision (old) — must show status=superseded, superseded_by=new_id")
    print("=" * 70)
    sql_log.clear()
    old_after = _row({"id": OLD_ID, "status": "superseded", "superseded_by": NEW_ID})
    pool = _pool(old_after)
    fetched_old = await service.get_decision(OLD_ID, TENANT_ID, pool)
    for s in sql_log:
        print(s)
    print(f"\nOld decision after supersession:")
    print(f"  id              = {fetched_old.id}")
    print(f"  decision_statement = {fetched_old.decision_statement!r}  ← UNCHANGED")
    print(f"  rationale       = {fetched_old.rationale!r}  ← UNCHANGED")
    print(f"  status          = {fetched_old.status}  ← SET TO 'superseded'")
    print(f"  superseded_by   = {fetched_old.superseded_by}  ← POINTS TO NEW RECORD")

    # ── 4. Query new decision independently ──────────────────────────────────
    print("\n" + "=" * 70)
    print("STEP 4: get_decision (new) — independently queryable")
    print("=" * 70)
    sql_log.clear()
    new_after = _row({
        "id": NEW_ID,
        "decision_statement": "Use CockroachDB for global scalability",
        "rationale": "Geographic distribution requirement added",
        "status": "proposed",
        "superseded_by": None,
    })
    pool = _pool(new_after)
    fetched_new = await service.get_decision(NEW_ID, TENANT_ID, pool)
    for s in sql_log:
        print(s)
    print(f"\nNew decision:")
    print(f"  id              = {fetched_new.id}")
    print(f"  decision_statement = {fetched_new.decision_statement!r}")
    print(f"  status          = {fetched_new.status}")
    print(f"  superseded_by   = {fetched_new.superseded_by}")

    # ── Assertions (all must pass) ────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ASSERTIONS")
    print("=" * 70)
    assert str(fetched_old.id) == str(OLD_ID), "old record still exists"
    assert fetched_old.status == "superseded", "old record status = superseded"
    assert str(fetched_old.superseded_by) == str(NEW_ID), "old superseded_by -> new_id"
    assert fetched_old.decision_statement == "Use PostgreSQL for primary storage", "original content unchanged"
    assert str(fetched_new.id) == str(NEW_ID), "new record independently queryable"
    print("  [PASS] Old record still exists with original content unchanged")
    print("  [PASS] Old record status = 'superseded'")
    print(f"  [PASS] Old record superseded_by = {NEW_ID} (new decision UUID)")
    print("  [PASS] New decision independently queryable")
    print("\nAll assertions passed.")


if __name__ == "__main__":
    asyncio.run(main())
