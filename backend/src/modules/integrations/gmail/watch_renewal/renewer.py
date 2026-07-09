"""
Gmail Watch API renewal logic - co-located with the Gmail connector.

Gmail push notification watches expire after 7 days and must be proactively
renewed. This module owns the renewal logic; jobs/cron/gmail_renewal.py calls
renew_all_watches() on a 6-day cron schedule.

The renewal flow:
  1. Query Supabase for all Slack sources with a watch_expiry within 48h.
  2. Call Gmail users.watch() to get a new expiry.
  3. Update the sources table with the new expiry timestamp.
"""
from __future__ import annotations
import logging

log = logging.getLogger(__name__)

RENEWAL_LOOKAHEAD_HOURS = 48  # Renew watches expiring within this window


async def renew_all_watches() -> None:
    """Renew Gmail watches for all connected workspaces approaching expiry."""
    sources = await _get_expiring_sources()
    log.info("Gmail watch renewal: %d watches to renew", len(sources))
    for source in sources:
        try:
            await _renew_single_watch(source)
        except Exception:
            log.exception("Failed to renew Gmail watch for source_id=%s", source.get("id"))


async def _get_expiring_sources() -> list[dict]:
    """Query sources table for Gmail connections whose watch expires within RENEWAL_LOOKAHEAD_HOURS."""
    # TODO: SELECT * FROM sources WHERE source_type='gmail'
    #       AND watch_expiry < NOW() + INTERVAL '48 hours'
    raise NotImplementedError


async def _renew_single_watch(source: dict) -> None:
    """Call Gmail users.watch() and update watch_expiry in sources table."""
    # TODO: call Gmail API, update sources SET watch_expiry=new_expiry WHERE id=source['id']
    raise NotImplementedError
