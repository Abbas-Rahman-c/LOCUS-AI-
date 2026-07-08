"""
Slack per-source rate-budget — tracks calls-per-minute against Slack API limits.

This module is co-located with the Slack connector it serves.
The ingestion worker checks the budget BEFORE making a Slack API call, not after
receiving a 429. This prevents wasted calls and avoids triggering Slack throttling.

Rate limit reference: Slack tier 3 = ~50 req/min per workspace.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

SLACK_RATE_LIMIT_PER_MINUTE = 50  # Tier 3 default


async def has_budget(workspace_id: str) -> bool:
    """Return True if this workspace has remaining Slack API budget for this minute window.
    
    Reads the rate_budgets table in Supabase, keyed on (workspace_id, source='slack', window_start).
    """
    # TODO: SELECT calls_this_minute FROM rate_budgets WHERE workspace_id=$1 AND source='slack'
    #       AND window_start = date_trunc('minute', NOW())
    raise NotImplementedError


async def consume_budget(workspace_id: str, calls: int = 1) -> None:
    """Increment the call counter for this workspace's current minute window.
    
    Called after a successful Slack API call. Uses an upsert so the row is created
    on first call of the minute.
    """
    # TODO: INSERT INTO rate_budgets ... ON CONFLICT DO UPDATE calls_this_minute += calls
    raise NotImplementedError


async def reset_expired_windows() -> None:
    """Clean up rate_budget rows older than 2 minutes (called by cleanup cron if desired)."""
    # TODO: DELETE FROM rate_budgets WHERE window_start < NOW() - INTERVAL '2 minutes'
    raise NotImplementedError
