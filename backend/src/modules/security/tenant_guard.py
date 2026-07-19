"""
Tenant isolation — Layer 2 of 2 (application-level pre-filter).

Every row returned from a DB query inside a request handler must pass through
assert_tenant_scope() before being returned to the caller.  This is the second
independent enforcement layer; a failure in Layer 1 (RLS) alone cannot leak
another tenant's data if Layer 2 is applied.

Why two layers?
    Database RLS is powerful but depends on set_config() being called correctly
    on every connection.  If a connection is ever acquired directly (bypassing
    tenant_conn), RLS fires with an empty tenant_id and the USING clause
    evaluates to false — blocking all rows, but not raising an error the caller
    would notice.  The application pre-filter makes the invariant explicit and
    testable in unit tests without a real database.

Usage:
    from modules.security.tenant_guard import assert_tenant_scope, TenantScopeError

    rows = await conn.fetch("SELECT id, tenant_id FROM decisions WHERE ...")
    for row in rows:
        assert_tenant_scope(row["tenant_id"], ctx.tenant_id)
"""
from __future__ import annotations

import uuid


class TenantScopeError(PermissionError):
    """Raised when a DB row belongs to a different tenant than the request."""


def assert_tenant_scope(
    row_tenant_id: uuid.UUID | str,
    ctx_tenant_id: uuid.UUID | str,
) -> None:
    """
    Raise TenantScopeError if the row's tenant_id does not match the request's
    tenant_id.

    This must be called on every row returned from a DB query inside a
    request-scoped path (decisions, search, MCP tools, etc.).

    Args:
        row_tenant_id: The tenant_id stored on the database row.
        ctx_tenant_id: The tenant_id from the caller's TenantContext.
    """
    if str(row_tenant_id) != str(ctx_tenant_id):
        raise TenantScopeError(
            "cross-tenant access denied: "
            f"row.tenant_id={row_tenant_id!r} != ctx.tenant_id={ctx_tenant_id!r}"
        )
