"""
APScheduler setup - cron expression ? function reference registry.

Rule: this file registers WHAT runs WHEN.
It must not contain HOW a job executes (retry policy, worker health checks, etc.).
Worker lifecycle logic lives in queue/workers/.
"""
from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from jobs.cleanup.purge_raw import run_purge_job
from jobs.cron.digest_cron import run_digest_job
from jobs.cron.gmail_renewal import run_gmail_renewal_job
from jobs.cron.notion_poller import run_notion_poll_job


def build_scheduler() -> AsyncIOScheduler:
    """Construct and register all cron jobs. Call start() on the returned scheduler."""
    scheduler = AsyncIOScheduler()

    # 30-day raw event purge - runs daily at 02:00 UTC
    scheduler.add_job(run_purge_job, CronTrigger(hour=2, minute=0), id="purge_raw_events")

    # Weekly Team Pulse digest - every Monday at 09:00 UTC
    scheduler.add_job(run_digest_job, CronTrigger(day_of_week="mon", hour=9, minute=0), id="weekly_digest")

    # Gmail watch renewal - every 6 days (watches expire at 7 days)
    scheduler.add_job(run_gmail_renewal_job, CronTrigger(day="*/6", hour=1, minute=0), id="gmail_watch_renewal")

    # Notion page poller - every 5 minutes
    scheduler.add_job(run_notion_poll_job, CronTrigger(minute="*/5"), id="notion_poller")

    return scheduler
