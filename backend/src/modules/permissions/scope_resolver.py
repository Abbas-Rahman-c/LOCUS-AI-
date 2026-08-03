"""
Permission Scope Resolver — the sole source of a caller's authorized
permission_scopes for /search. Never trust a request body for this: scopes
are authorization data, and a client asking for a scope is not evidence it
is entitled to it.

There is still no real per-user/per-channel ACL table anywhere in the
schema (memberships stores only tenant_id/user_id/role - nothing
scope-shaped), so this cannot grant broad, inferred scopes. What it can do
safely: the connectors (gmail-manual-sync/slack-webhook/notion-poller) set
a decision's permission_scope to an identifier the caller can independently
be shown to own - the connected Gmail account's own email address, for
example. Resolving the caller's own linked identifiers as their scope lets
them see decisions provably tied to their own connected accounts, without
inferring any broader (e.g. whole-channel, whole-workspace) access. Scopes
tied to identifiers not owned by the caller remain fails-closed exactly as
before.
"""
from __future__ import annotations

import uuid

from app.dependencies import TenantContext


async def resolve_permission_scopes(ctx: TenantContext) -> list[str]:
    """Return the caller's authorized permission_scopes, derived only from
    the authenticated TenantContext - never from request input.

    Currently: the caller's own auth email address, if resolvable, so
    decisions scoped to their own connected account (e.g. their Gmail
    address, which is exactly what gmail-manual-sync sets as
    permission_scope) become visible to them. Everything else - decisions
    with an empty scope (workspace-wide) - is already visible regardless,
    via is_decision_accessible()'s existing empty-scope-is-public rule.
    """
    from database.pool import get_admin_db_pool

    async with get_admin_db_pool().acquire() as conn:
        email = await conn.fetchval(
            "SELECT email FROM auth.users WHERE id = $1",
            uuid.UUID(ctx.user_id),
        )

    return [email] if email else []
