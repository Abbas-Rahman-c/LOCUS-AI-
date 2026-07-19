"""
Unit tests for modules.permissions.scope_resolver.resolve_permission_scopes().

Proves the resolver derives scopes only from the authenticated
TenantContext and never grants a non-empty scope to any role - matching
the repository evidence that no user-to-scope mapping exists anywhere in
this codebase (see the module's own docstring for the citations).
"""
from __future__ import annotations

import pytest

from app.dependencies import TenantContext
from modules.permissions.scope_resolver import resolve_permission_scopes


class TestResolvePermissionScopes:
    @pytest.mark.parametrize("role", ["member", "owner", "admin"])
    def test_always_returns_empty_scopes_regardless_of_role(self, role):
        """No repository evidence supports owner/admin (or any role)
        receiving a non-empty scope, so every role resolves to []."""
        ctx = TenantContext(user_id="user-1", tenant_id="tenant-1", role=role)
        assert resolve_permission_scopes(ctx) == []

    def test_ignores_everything_except_the_authenticated_context(self):
        """The function signature accepts only a TenantContext - there is
        no request-derived input it could trust even if one were passed."""
        ctx_a = TenantContext(user_id="user-1", tenant_id="tenant-1", role="member")
        ctx_b = TenantContext(user_id="user-2", tenant_id="tenant-2", role="owner")
        assert resolve_permission_scopes(ctx_a) == resolve_permission_scopes(ctx_b) == []
