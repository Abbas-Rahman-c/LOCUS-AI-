"""
Cleanup cron entry point - 30-day raw event purge.

This file contains ONLY the schedule registration.
All business logic (the actual DELETE query, encryption-key cleanup) lives in:
  modules/ingestion/raw-events/store.py ? purge_expired_raw_events()
"""
import logging
from modules.ingestion.raw_events.store import purge_expired_raw_events

log = logging.getLogger(__name__)


async def run_purge_job() -> None:
    """Thin wrapper called by the APScheduler cron trigger."""
    log.info("[cron] raw-event purge job started")
    deleted = await purge_expired_raw_events()
    log.info("[cron] raw-event purge job complete - %d records deleted", deleted)
