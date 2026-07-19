"""
Permission Repository — the authorization predicate over one retrieved
decision: overlapping permission_scope for the authenticated caller.

Pure, DB-free rule evaluation. Tenant boundaries are already enforced by
RLS inside modules.retrieval.vector.repository (Layer 1) before any row
ever reaches this module - this is the second, independent authorization
axis RLS does not cover (which sub-tenant scopes, e.g. Slack channels, a
specific caller may see), not a re-check of tenant_id.
"""
from __future__ import annotations

from modules.retrieval.vector.schemas import RetrievalMatch


def is_decision_accessible(permission_scopes: list[str], decision: RetrievalMatch) -> bool:
    """True iff decision.permission_scope overlaps the caller's permission_scopes.

    An empty permission_scope on either side can never overlap with
    anything, so it is always rejected - never silently allowed through.
    """
    return bool(set(decision.permission_scope) & set(permission_scopes))
