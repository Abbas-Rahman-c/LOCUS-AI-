"""
Maps decision IDs to source permalinks (Slack thread URL, Notion block,
email ID) via public.decision_sources.

A decision can have more than one decision_sources row -- e.g. re-affirmed
across multiple threads, or (per DecisionWriteRequest.source_permalink
being Optional) sometimes none at all, if it was persisted without an
origin permalink. resolve_permalinks() picks the most recently recorded
permalink per decision as "the" citation link; callers that need every
known source for a decision should query decision_sources directly rather
than go through this module.

Kept as its own module (rather than a join inside hybrid.py) because it is
only ever needed for the final, already-ranked top_k -- not the full
candidate pool either search leg considered -- and because the eval
harness needs a resolver call with an *identical* signature whether the
answer came from the real pipeline or scenario_packs.json's
source_permalink field (see modules.retrieval.evaluation.mock_pipeline).
"""
from __future__ import annotations

import logging
from uuid import UUID

import asyncpg

from database.pool import get_db_pool
from modules.retrieval.schemas import Citation
from modules.security.tenant_guard import set_current_tenant_id

log = logging.getLogger(__name__)


class ResolverError(Exception):
    """Raised when the permalink lookup query fails."""


async def resolve_permalinks(
    decision_ids: list[UUID],
    tenant_id: UUID,
    *,
    pool: asyncpg.Pool | None = None,
) -> dict[UUID, str | None]:
    """Batch-resolves decision_id -> most-recent permalink (or None if the
    decision has no decision_sources row). Every id in `decision_ids` is a
    key in the returned dict, even ones with no permalink -- callers should
    never need a .get() with a default here.

    Tenant-scoped the same way hybrid.py's legs are: explicit tenant_id
    predicate plus the RLS GUC, so a decision_id belonging to another
    tenant resolves to None rather than that tenant's permalink.
    """
    if tenant_id is None:
        raise ValueError("resolve_permalinks() requires a non-null tenant_id")
    resolved: dict[UUID, str | None] = {decision_id: None for decision_id in decision_ids}
    if not decision_ids:
        return resolved

    db_pool = pool if pool is not None else get_db_pool()

    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                await set_current_tenant_id(conn, tenant_id)
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT ON (decision_id) decision_id, permalink
                    FROM public.decision_sources
                    WHERE tenant_id = $1 AND decision_id = ANY($2::uuid[])
                    ORDER BY decision_id, created_at DESC
                    """,
                    tenant_id,
                    decision_ids,
                )
    except asyncpg.PostgresError as exc:
        raise ResolverError(f"Failed to resolve permalinks: {exc}") from exc

    for row in rows:
        resolved[row["decision_id"]] = row["permalink"]

    log.debug(
        "resolve_permalinks tenant_id=%s requested=%d resolved=%d",
        tenant_id, len(decision_ids), sum(1 for v in resolved.values() if v is not None),
    )
    return resolved


async def resolve_citations(
    decision_ids: list[UUID],
    tenant_id: UUID,
    *,
    pool: asyncpg.Pool | None = None,
) -> list[Citation]:
    """Convenience wrapper returning Citation objects in the same order as
    `decision_ids` -- what modules.retrieval.synthesis.synthesizer attaches
    to a SynthesizedAnswer."""
    permalinks = await resolve_permalinks(decision_ids, tenant_id, pool=pool)
    return [
        Citation(decision_id=decision_id, permalink=permalinks[decision_id])
        for decision_id in decision_ids
    ]
