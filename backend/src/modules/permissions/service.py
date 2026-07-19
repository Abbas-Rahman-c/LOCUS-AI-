"""
Permission Service — Layer 2 authorization, applied strictly after
tenant-scoped RLS retrieval (Layer 1). filter_accessible_decisions() is the
single choke point every retrieval endpoint calls before handing decisions
to context building or Claude - never queries the database and never
authenticates anyone, only filters a list already in memory (and already
tenant-scoped) by permission_scope overlap.
"""
from __future__ import annotations

import logging
import time

from modules.permissions.repository import is_decision_accessible
from modules.retrieval.vector.schemas import RetrievalMatch

log = logging.getLogger(__name__)


def filter_accessible_decisions(
    permission_scopes: list[str],
    retrieved_decisions: list[RetrievalMatch],
) -> list[RetrievalMatch]:
    """Return only the decisions whose permission_scope overlaps permission_scopes.

    Tenant filtering must already be enforced before this function ever
    receives retrieved_decisions (RLS + the explicit tenant_id predicate in
    modules.retrieval.vector.repository) - this only ever narrows further
    within that already-tenant-scoped set. Logs retrieved/authorized/
    rejected counts and filtering time (ms) on every call.
    """
    start = time.perf_counter()

    accessible = [
        decision
        for decision in retrieved_decisions
        if is_decision_accessible(permission_scopes, decision)
    ]

    elapsed_ms = (time.perf_counter() - start) * 1000
    retrieved_count = len(retrieved_decisions)
    authorized_count = len(accessible)
    rejected_count = retrieved_count - authorized_count

    log.info(
        "Permission filter: retrieved=%d authorized=%d rejected=%d filtering_time_ms=%.3f",
        retrieved_count,
        authorized_count,
        rejected_count,
        elapsed_ms,
    )

    return accessible
