"""
Unit tests for the decisions service verifying tenant isolation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest

from tests.conftest import make_pool_with_rows
from modules.decisions import service
from modules.security.tenant_guard import TenantScopeError

def test_list_decisions_filters_by_tenant():
    """Verify that listing decisions scoped to tenant A only fetches tenant A's rows."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    # DB records representing decisions
    decisions_in_db = [
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_a,
            "record_type": "decision",
            "decision_statement": "Decision A1",
            "rationale": "Rationale A1",
            "status": "decided",
            "scope": "team",
            "confidence": 0.95,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_a,
            "record_type": "decision",
            "decision_statement": "Decision A2",
            "rationale": "Rationale A2",
            "status": "proposed",
            "scope": "team",
            "confidence": 0.85,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    ]

    pool = make_pool_with_rows(decisions_in_db, scalar=2)

    async def run_test():
        res = await service.list_decisions(tenant_a, pool)
        assert len(res.items) == 2
        assert res.total == 2
        assert res.items[0].decision_statement == "Decision A1"
        assert res.items[1].decision_statement == "Decision A2"

    import asyncio
    asyncio.run(run_test())

def test_list_decisions_fails_on_tenant_leak():
    """If the database driver returns a record from tenant B during a tenant A query,
    assert_tenant_scope (Layer 2) must raise TenantScopeError.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    leaked_records = [
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_b,  # Tenant B's record leaked!
            "record_type": "decision",
            "decision_statement": "Leaked Decision",
            "rationale": "Should not be here",
            "status": "proposed",
            "scope": "team",
            "confidence": 0.5,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    ]

    pool = make_pool_with_rows(leaked_records, scalar=1)

    async def run_test():
        with pytest.raises(TenantScopeError):
            await service.list_decisions(tenant_a, pool)

    import asyncio
    asyncio.run(run_test())

def test_get_decision_filters_by_tenant():
    """Verify that fetching a single decision checks its tenant_id."""
    tenant_a = uuid.uuid4()
    decision_id = uuid.uuid4()

    record = {
        "id": decision_id,
        "tenant_id": tenant_a,
        "record_type": "decision",
        "decision_statement": "Decision Statement",
        "rationale": "Rationale text",
        "status": "proposed",
        "scope": "team",
        "confidence": 0.85,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    pool = make_pool_with_rows([record])

    async def run_test():
        res = await service.get_decision(decision_id, tenant_a, pool)
        assert res is not None
        assert res.id == decision_id
        assert res.tenant_id == tenant_a

    import asyncio
    asyncio.run(run_test())

def test_get_decision_returns_none_for_wrong_tenant():
    """Verify that fetching a decision from tenant B as tenant A returns None,
    preventing ID existence checking.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    decision_id = uuid.uuid4()

    # The query checks both id AND tenant_id, so the DB returns no rows if they mismatch.
    pool = make_pool_with_rows([])

    async def run_test():
        res = await service.get_decision(decision_id, tenant_a, pool)
        assert res is None

    import asyncio
    asyncio.run(run_test())
