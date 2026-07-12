"""Encrypted raw-event persistence and retention cleanup."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from database.connection import get_db_pool
from modules.security.encryption import encrypt_data

log = logging.getLogger(__name__)


async def store_raw_event(envelope: dict, connection_id: uuid.UUID | None = None) -> str:
    """Encrypt and persist an event, returning its record ID."""
    tenant_id = envelope.get("tenant_id")
    if isinstance(tenant_id, str):
        tenant_id = uuid.UUID(tenant_id)
        
    if connection_id is None and "connection_id" in envelope:
        conn_id = envelope["connection_id"]
        if conn_id:
            connection_id = uuid.UUID(str(conn_id))

    record_id = str(uuid.uuid4())
    async with get_db_pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO raw_events (
                   id, tenant_id, connection_id, source, source_id, 
                   thread_ref, permission_scope, raw_content, received_at
               )
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())""",
            record_id, 
            tenant_id, 
            connection_id, 
            envelope.get("source", "gmail"), 
            envelope.get("source_id"),
            envelope.get("thread_ref"),
            envelope.get("permission_scope", []),
            encrypt_data(json.dumps(envelope)),
        )
    return record_id


async def purge_expired_raw_events() -> int:
    """Delete raw events older than the retention period using expires_at column."""
    async with get_db_pool().acquire() as conn:
        result = await conn.execute("DELETE FROM raw_events WHERE expires_at < NOW()")
    return int(result.split()[1]) if result and result.startswith("DELETE ") else 0
