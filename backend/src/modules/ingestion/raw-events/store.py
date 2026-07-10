"""
Raw event store - encrypted write with 30-day TTL + purge function.

This module owns ALL business logic for raw event storage and cleanup.
The jobs/cleanup/ cron entry point imports purge_expired_raw_events() from here.
"""
from __future__ import annotations
import logging
import json
import uuid
from datetime import datetime, timedelta, timezone

from database.connection import get_db_pool
from modules.security.encryption import encrypt_data

log = logging.getLogger(__name__)

RAW_EVENT_TTL_DAYS = 30


async def store_raw_event(envelope: dict) -> str:
    """Encrypt and persist a raw event. Returns the stored record ID.
    
    Encryption: AES-GCM via modules/security/encryption.py.
    TTL is enforced by a Postgres scheduled job (see database/sql/functions.sql).
    """
    serialized = json.dumps(envelope)
    encrypted_payload = encrypt_data(serialized)
    
    pool = get_db_pool()
    record_id = str(uuid.uuid4())
    
    # Extract metadata from envelope
    # Standard EventEnvelope has tenant_id, source, source_id
    workspace_id = envelope.get("tenant_id")
    if isinstance(workspace_id, str):
        workspace_id = uuid.UUID(workspace_id)
        
    source = envelope.get("source", "gmail")
    source_id = envelope.get("source_id")
    
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO raw_events (id, workspace_id, source, source_id, payload, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            """,
            record_id, workspace_id, source, source_id, encrypted_payload
        )
    log.info("Stored raw event source=%s source_id=%s with ID=%s", source, source_id, record_id)
    return record_id


async def purge_expired_raw_events() -> int:
    """Delete all raw events older than RAW_EVENT_TTL_DAYS (30 days).
    
    This is the canonical implementation of the purge logic.
    Called by jobs/cleanup/ on a cron schedule - no SQL lives in jobs/.

    Returns:
        Number of records deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=RAW_EVENT_TTL_DAYS)
    log.info("Purging raw events older than %s (cutoff: %s)", RAW_EVENT_TTL_DAYS, cutoff)

    pool = get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM raw_events WHERE created_at < $1",
            cutoff
        )
        deleted_count = 0
        if result and result.startswith("DELETE "):
            try:
                deleted_count = int(result.split(" ")[1])
            except ValueError:
                pass
                
    log.info("Purged %d raw events", deleted_count)
    return deleted_count
