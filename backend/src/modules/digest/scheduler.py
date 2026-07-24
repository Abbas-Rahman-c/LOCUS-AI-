"""
Digest Scheduler — Monday 09:00 UTC delivery trigger.

This module provides the trigger function that pg_cron calls on a Monday
morning schedule to kick off the weekly Team Pulse generation.

Pattern: identical to the Notion poller and Gmail watch renewal — a
pg_cron job calls a Supabase Edge Function via HTTP, which runs the
digest for every active tenant. This keeps the scheduling concern in
Postgres (where it can survive backend restarts) while the actual work
runs in the Edge Function runtime.

pg_cron job (to be added via migration or Supabase dashboard):

    SELECT cron.schedule(
        'weekly-team-pulse',           -- job name
        '0 9 * * 1',                   -- every Monday at 09:00 UTC
        $$
        SELECT net.http_post(
            url  := current_setting('app.supabase_url') || '/functions/v1/team-pulse-trigger',
            body := '{}'::jsonb
        );
        $$
    );

The Edge Function (supabase/functions/team-pulse-trigger/index.ts) will
iterate over all active tenants in source_connections and call
generate_team_pulse() for each — or, for the MVP, it simply marks the
digest as "ready" in the DB so the frontend can fetch it on next load.

For the MVP, the GET /digest endpoint is the delivery mechanism —
the frontend TeamPulse.tsx page pulls it on demand. Push delivery
(email/Slack notification) is a follow-up once the schema supports it.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def get_cron_schedule() -> str:
    """Return the cron expression for the Monday 09:00 UTC trigger.

    Used by any tooling that programmatically registers pg_cron jobs.
    """
    return "0 9 * * 1"  # Every Monday at 09:00 UTC


async def trigger_weekly_digest() -> None:
    """Entrypoint called by the pg_cron/Edge Function trigger.

    For the MVP this is a no-op placeholder — the digest is generated
    on-demand by GET /digest. When push delivery is added, this function
    will iterate active tenants and enqueue digest generation jobs.
    """
    log.info("Weekly Team Pulse trigger fired (MVP: on-demand delivery via GET /digest)")
