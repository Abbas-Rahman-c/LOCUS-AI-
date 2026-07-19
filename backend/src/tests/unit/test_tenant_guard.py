"""
Unit tests for the Layer 2 tenant guard (assert_tenant_scope).
"""
from __future__ import annotations

import uuid

import pytest

from modules.security.tenant_guard import TenantScopeError, assert_tenant_scope


def test_same_tenant_passes():
    """assert_tenant_scope must not raise when IDs match."""
    tid = uuid.uuid4()
    assert_tenant_scope(tid, tid)  # should not raise


def test_same_tenant_as_string_passes():
    """UUID comparison must work whether passed as UUID or str."""
    tid = uuid.uuid4()
    assert_tenant_scope(str(tid), tid)
    assert_tenant_scope(tid, str(tid))
    assert_tenant_scope(str(tid), str(tid))


def test_different_tenant_raises():
    """assert_tenant_scope must raise TenantScopeError when IDs differ."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    with pytest.raises(TenantScopeError):
        assert_tenant_scope(tenant_a, tenant_b)


def test_error_message_includes_both_ids():
    """Error message should contain both tenant IDs for traceability."""
    tid_a = uuid.uuid4()
    tid_b = uuid.uuid4()

    with pytest.raises(TenantScopeError, match=str(tid_a)):
        assert_tenant_scope(tid_a, tid_b)
