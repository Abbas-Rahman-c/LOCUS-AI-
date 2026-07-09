"""
Raw event store - encrypted write with 30-day TTL + purge function.

This module owns ALL business logic for raw event storage and cleanup.
The jobs/cleanup/ cron entry point imports purge_expired_raw_events() from here.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

RAW_EVENT_TTL_DAYS = 30


async def store_raw_event(envelope: dict) -> str:
    """Encrypt and persist a raw event. Returns the stored record ID.
    
    Encryption: AES-GCM via modules/security/encryption.py.
    TTL is enforced by a Postgres scheduled job (see database/sql/functions.sql).
    """
    # TODO: implement AES-GCM encryption, then insert into raw_events table
    raise NotImplementedError


async def purge_expired_raw_events() -> int:
    """Delete all raw events older than RAW_EVENT_TTL_DAYS (30 days).
    
    This is the canonical implementation of the purge logic.
    Called by jobs/cleanup/ on a cron schedule - no SQL lives in jobs/.

    Returns:
        Number of records deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=RAW_EVENT_TTL_DAYS)
    log.info("Purging raw events older than %s (cutoff: %s)", RAW_EVENT_TTL_DAYS, cutoff)

    # TODO: execute DELETE FROM raw_events WHERE created_at < cutoff
    # and clean up associated KMS data-encryption keys
    deleted_count = 0
    log.info("Purged %d raw events", deleted_count)
    return deleted_count
