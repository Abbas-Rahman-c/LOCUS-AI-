"""
Permission Scope Resolver — the sole source of a caller's authorized
permission_scopes for /search. Never trust a request body for this: scopes
are authorization data, and a client asking for a scope is not evidence it
is entitled to it.

Repository evidence (gathered across modules.ingestion.envelope.schemas.
EventEnvelope's permission_scope field description, modules.ingestion.
envelope.normalizer.normalize_gmail_message, tests/unit/test_gmail.py, and
migrations/007_memberships_rls.sql) establishes:

  - public.memberships stores only tenant_id, user_id, and role - no scope
    list, no channel/source-access mapping, nothing scope-shaped.
  - No table anywhere (memberships, a channel-membership table, a
    per-user source-access table) maps a user or role to a non-empty
    permission_scope value.
  - No code path in modules.integrations.slack, modules.integrations.notion,
    or modules.integrations.gmail ever assigns a decision a non-empty
    permission_scope. The only ingestion pipeline that exists (Gmail)
    always sets permission_scope=[] ("empty = workspace-wide").
  - No existing code grants owner/admin roles broader visibility than
    ordinary members anywhere in modules.decisions.router/service or
    elsewhere - membership.role is surfaced (JWT claim, logging) but never
    used as an access-control predicate.

Given that evidence, every authenticated tenant member - regardless of
role - is proven to be authorized for exactly the workspace-wide scope.
This function intentionally always returns an empty list rather than
inferring any non-empty scope: modules.permissions.repository.
is_decision_accessible() already treats an empty decision.permission_scope
as accessible to everyone, so this fails closed on every decision that
carries a real (non-empty) scope, exactly as required until a genuine
per-user scope source is added to the schema.
"""
from __future__ import annotations

from app.dependencies import TenantContext


def resolve_permission_scopes(ctx: TenantContext) -> list[str]:
    """Return the caller's authorized permission_scopes, derived only from
    the authenticated TenantContext - never from request input.

    Always returns [] today: no repository evidence supports granting any
    user or role a non-empty scope. When a real per-user scope source is
    added to the schema, this is the only function that should change.
    """
    return []
