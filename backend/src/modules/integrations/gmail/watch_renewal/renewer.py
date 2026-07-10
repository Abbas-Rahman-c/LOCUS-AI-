"""
Gmail Watch API renewal logic  co-located with the Gmail connector.

Gmail push notification watches expire after 7 days and must be proactively
renewed. This module owns the renewal logic; jobs/cron/gmail_renewal.py calls
renew_all_watches() on a 6-day cron schedule.

The renewal flow:
  1. Query Supabase for all Slack sources with a watch_expiry within 48h.
  2. Call Gmail users.watch() to get a new expiry.
  3. Update the sources table with the new expiry timestamp.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from common.config import get_gmail_settings
from database.connection import get_db_pool
from modules.integrations.gmail.service import _get_valid_access_token

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
    cutoff = datetime.now(timezone.utc) + timedelta(hours=RENEWAL_LOOKAHEAD_HOURS)
    pool = get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, workspace_id, config, watch_expiry
            FROM sources
            WHERE source_type = 'gmail'
              AND status = 'active'
              AND watch_expiry IS NOT NULL
              AND watch_expiry <= $1
            ORDER BY watch_expiry ASC
            """,
            cutoff,
        )
    return [dict(row) for row in rows]


async def _renew_single_watch(source: dict) -> None:
    """Call Gmail users.watch() and update watch_expiry in sources table."""
    source_id = source["id"]
    pool = get_db_pool()
    settings = get_gmail_settings()

    async with pool.acquire() as conn:
        access_token = await _get_valid_access_token(source_id, conn)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/watch",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "topicName": settings.gmail_pubsub_topic,
                    "labelIds": ["INBOX"],
                },
            )
            if resp.status_code != 200:
                log.error("Failed to renew Gmail watch for source_id=%s: %s", source_id, resp.text)
                raise RuntimeError(f"Gmail watch renewal failed: {resp.text}")

            watch_data: dict[str, Any] = resp.json()
            history_id = watch_data.get("historyId")
            expiration_ms = int(watch_data.get("expiration", 0))
            if expiration_ms <= 0:
                raise RuntimeError("Gmail watch renewal response did not include a valid expiration")

            watch_expiry = datetime.fromtimestamp(expiration_ms / 1000.0, tz=timezone.utc)
            config = source.get("config") or {}
            if isinstance(config, str):
                config = json.loads(config)
            if history_id:
                config["history_id"] = history_id

            await conn.execute(
                """
                UPDATE sources
                SET watch_expiry = $1, config = $2::jsonb
                WHERE id = $3
                """,
                watch_expiry,
                json.dumps(config),
                source_id,
            )

            log.info(
                "Renewed Gmail watch for source_id=%s, historyId=%s, expires=%s",
                source_id,
                history_id,
                watch_expiry,
            )

