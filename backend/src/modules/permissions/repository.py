"""
Permission Repository — the authorization predicate over one retrieved
decision: workspace-wide visibility, or overlapping permission_scope for
the authenticated caller.

Pure, DB-free rule evaluation. Tenant boundaries are already enforced by
RLS inside modules.retrieval.vector.repository (Layer 1) before any row
ever reaches this module - this is the second, independent authorization
axis RLS does not cover (which sub-tenant scopes, e.g. Slack channels, a
specific caller may see), not a re-check of tenant_id.

Repository evidence for the empty-scope rule (modules.ingestion.envelope.
schemas.EventEnvelope.permission_scope's field description, confirmed by
modules.ingestion.envelope.normalizer.normalize_gmail_message and by
tests/unit/test_gmail.py's own assertion) is unambiguous: an empty
permission_scope means "workspace-wide" - visible to every tenant member -
not "inaccessible". Every decision ingested by the only pipeline that
exists today (Gmail) has permission_scope == [] for exactly this reason.
"""
from __future__ import annotations

from modules.retrieval.vector.schemas import RetrievalMatch


def is_decision_accessible(permission_scopes: list[str], decision: RetrievalMatch) -> bool:
    """True iff the decision is workspace-wide, or its permission_scope
    overlaps the caller's permission_scopes.

    An empty decision.permission_scope is workspace-wide and is always
    accessible, regardless of the caller's scopes (see module docstring
    for the repository evidence). A non-empty decision.permission_scope
    requires an actual overlap with the caller's permission_scopes - an
    empty caller scope list can never satisfy that, so non-empty-scoped
    decisions are rejected whenever the caller has no proven scopes.
    """
    if not decision.permission_scope:
        return True
    return bool(set(decision.permission_scope) & set(permission_scopes))
