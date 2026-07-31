"""
Unit tests for modules.permissions.scope_resolver.resolve_permission_scopes().

Proves the resolver derives scopes only from the authenticated
TenantContext's own linked auth email - never from request input, and never
a broader/inferred scope than "identifiers this specific caller owns".
"""
from __future__ import annotations
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dependencies import TenantContext
from modules.permissions.scope_resolver import resolve_permission_scopes


def _mock_admin_pool(email: str | None):
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=email)

    mock_acquire_cm = AsyncMock()
    mock_acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire_cm.__aexit__ = AsyncMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_acquire_cm)
    return mock_pool


class TestResolvePermissionScopes:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ["member", "owner", "admin"])
    async def test_returns_callers_own_email_regardless_of_role(self, role):
        """role never changes the outcome - only the caller's own linked
        email does, since role is not (and must not become) an access-
        control predicate here."""
        ctx = TenantContext(user_id=str(uuid.uuid4()), tenant_id="tenant-1", role=role)
        with patch(
            "database.pool.get_admin_db_pool",
            return_value=_mock_admin_pool("person@example.com"),
        ):
            assert await resolve_permission_scopes(ctx) == ["person@example.com"]

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_email_resolvable(self):
        """No repository evidence supports inferring a scope beyond the
        caller's own identity - an unresolvable email means []."""
        ctx = TenantContext(user_id=str(uuid.uuid4()), tenant_id="tenant-1", role="member")
        with patch("database.pool.get_admin_db_pool", return_value=_mock_admin_pool(None)):
            assert await resolve_permission_scopes(ctx) == []

    @pytest.mark.asyncio
    async def test_different_callers_get_their_own_distinct_scope(self):
        """Each caller is scoped to their own identity, not to a shared or
        tenant-wide value."""
        ctx_a = TenantContext(user_id=str(uuid.uuid4()), tenant_id="tenant-1", role="member")
        ctx_b = TenantContext(user_id=str(uuid.uuid4()), tenant_id="tenant-1", role="owner")

        with patch("database.pool.get_admin_db_pool", return_value=_mock_admin_pool("a@example.com")):
            scopes_a = await resolve_permission_scopes(ctx_a)
        with patch("database.pool.get_admin_db_pool", return_value=_mock_admin_pool("b@example.com")):
            scopes_b = await resolve_permission_scopes(ctx_b)

        assert scopes_a == ["a@example.com"]
        assert scopes_b == ["b@example.com"]
        assert scopes_a != scopes_b
