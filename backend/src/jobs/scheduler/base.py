"""
APScheduler setup — cron expression -> function reference registry.

Rule: this file registers WHAT runs WHEN.
It must not contain HOW a job executes (retry policy, worker health checks, etc.).
Worker lifecycle logic lives in queue/workers/.

Gmail watch renewal and Notion polling are intentionally NOT registered here.
Both are superseded by the real, live Supabase Edge Functions (gmail-oauth's
watch mechanism, notion-poller) scheduled directly via pg_cron in Postgres —
the Python versions (jobs/cron/gmail_renewal.py, jobs/cron/notion_poller.py)
are legacy, unmaintained, and notion_poller.py's underlying business logic is
still a NotImplementedError stub. Registering them here would either crash on
import (gmail_renewal depends on the now-removed integrations/gmail/service.py)
or throw on every scheduled run (Notion poller). Do not re-add them without
first fixing the underlying implementations for real.
"""
from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from jobs.cleanup.purge_raw import run_purge_job
from jobs.cron.digest_cron import run_digest_job


def build_scheduler() -> AsyncIOScheduler:
    """Construct and register all cron jobs. Call start() on the returned scheduler."""
    scheduler = AsyncIOScheduler()

    # 30-day raw event purge — runs daily at 02:00 UTC
    scheduler.add_job(run_purge_job, CronTrigger(hour=2, minute=0), id="purge_raw_events")

    # Weekly Team Pulse digest — every Monday at 09:00 UTC
    # Generates + persists digests for all tenants (see jobs/cron/digest_cron.py).
    # Must be started from the worker process (queues/workers/run.py), not each
    # API replica, to avoid duplicate Monday runs.
    scheduler.add_job(run_digest_job, CronTrigger(day_of_week="mon", hour=9, minute=0), id="weekly_digest")

    return scheduler