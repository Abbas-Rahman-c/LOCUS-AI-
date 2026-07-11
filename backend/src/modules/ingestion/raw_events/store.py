"""Encrypted raw-event persistence and retention cleanup."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from database.connection import get_db_pool
from modules.security.encryption import encrypt_data

log = logging.getLogger(__name__)
RAW_EVENT_TTL_DAYS = 30


async def store_raw_event(envelope: dict) -> str:
    """Encrypt and persist an event, returning its record ID."""
    workspace_id = envelope.get("tenant_id")
    if isinstance(workspace_id, str):
        workspace_id = uuid.UUID(workspace_id)
    record_id = str(uuid.uuid4())
    async with get_db_pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO raw_events (id, workspace_id, source, source_id, payload, created_at)
               VALUES ($1, $2, $3, $4, $5, NOW())""",
            record_id, workspace_id, envelope.get("source", "gmail"), envelope.get("source_id"),
            encrypt_data(json.dumps(envelope)),
        )
    return record_id


async def purge_expired_raw_events() -> int:
    """Delete raw events older than the retention period."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RAW_EVENT_TTL_DAYS)
    async with get_db_pool().acquire() as conn:
        result = await conn.execute("DELETE FROM raw_events WHERE created_at < $1", cutoff)
    return int(result.split()[1]) if result and result.startswith("DELETE ") else 0
