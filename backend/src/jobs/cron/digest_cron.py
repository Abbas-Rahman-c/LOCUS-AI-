"""
Digest cron entry point.

Business logic: for each active tenant, generate team (+ personal) digests
via modules.digest.service.generate_team_pulse(), then persist via
modules.digest.store.save_weekly_digest().

Called by APScheduler every Monday at 09:00 UTC (jobs/scheduler/base.py).
"""
from __future__ import annotations

import logging
import uuid

from database.pool import get_admin_db_pool, get_db_pool
from modules.digest.service import generate_team_pulse
from modules.digest.store import digest_week_of, save_weekly_digest

log = logging.getLogger(__name__)


async def _list_active_tenants() -> list[uuid.UUID]:
    """All tenant ids (admin pool — cross-tenant listing bypasses RLS)."""
    admin = get_admin_db_pool()
    async with admin.acquire() as conn:
        rows = await conn.fetch("SELECT id FROM tenants ORDER BY created_at")
    return [row["id"] for row in rows]


async def _list_tenant_members(tenant_id: uuid.UUID) -> list[uuid.UUID]:
    """Auth user ids with membership in this tenant (admin pool)."""
    admin = get_admin_db_pool()
    async with admin.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id FROM memberships WHERE tenant_id = $1",
            tenant_id,
        )
    return [row["user_id"] for row in rows]


async def run_digest_job() -> None:
    """Generate and persist weekly digests for every tenant.

    Permission scopes are [] for all members today (see scope_resolver).
    Failures on one tenant/member are logged and skipped so the rest continue.
    """
    log.info("[cron] weekly digest job started")
    week_of = digest_week_of()
    pool = get_db_pool()

    try:
        tenant_ids = await _list_active_tenants()
    except Exception:
        log.exception("[cron] failed to list tenants — aborting digest job")
        return

    log.info("[cron] generating digests for %d tenant(s) week_of=%s", len(tenant_ids), week_of)

    for tenant_id in tenant_ids:
        # Team Pulse (one per tenant)
        try:
            team_digest = await generate_team_pulse(
                pool, tenant_id, permission_scopes=[], scope="team"
            )
            await save_weekly_digest(pool, tenant_id, team_digest, week_of)
            log.info("[cron] team digest saved tenant=%s", tenant_id)
        except Exception:
            log.exception("[cron] team digest failed tenant=%s", tenant_id)

        # Personal digests (one per member)
        try:
            member_ids = await _list_tenant_members(tenant_id)
        except Exception:
            log.exception("[cron] list members failed tenant=%s", tenant_id)
            continue

        for user_id in member_ids:
            try:
                personal = await generate_team_pulse(
                    pool,
                    tenant_id,
                    permission_scopes=[],
                    scope="personal",
                    user_id=user_id,
                )
                await save_weekly_digest(
                    pool, tenant_id, personal, week_of, user_id=user_id
                )
                log.info(
                    "[cron] personal digest saved tenant=%s user=%s",
                    tenant_id,
                    user_id,
                )
            except Exception:
                log.exception(
                    "[cron] personal digest failed tenant=%s user=%s",
                    tenant_id,
                    user_id,
                )

    log.info("[cron] weekly digest job complete")
