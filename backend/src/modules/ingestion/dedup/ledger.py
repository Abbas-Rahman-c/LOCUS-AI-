"""
Dedup ledger (Section 1.5) backed by public.raw_events (Section 1.6).

Key: UNIQUE (tenant_id, source, source_id) on public.raw_events.
is_duplicate / mark_seen are the only ingestion-layer idempotency API.
Persistence + encryption live in modules.ingestion.raw_events.store.
"""
from __future__ import annotations

import logging
import uuid

from database.tenant_context import tenant_connection
from modules.ingestion.raw_events.store import store_raw_event

log = logging.getLogger(__name__)


def _require_str(payload: dict, key: str) -> str:
    value = payload.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"envelope missing required field: {key}")
    return str(value)


def _parse_tenant_id(payload: dict) -> uuid.UUID:
    return uuid.UUID(_require_str(payload, "tenant_id"))


async def is_duplicate(payload: dict) -> bool:
    """Return True if (tenant_id, source, source_id) already exists in raw_events."""
    tenant_id = _parse_tenant_id(payload)
    source = _require_str(payload, "source")
    source_id = _require_str(payload, "source_id")

    async with tenant_connection(tenant_id) as conn:
        exists = await conn.fetchval(
            """
            select exists(
              select 1
              from public.raw_events
              where tenant_id = $1
                and source = $2
                and source_id = $3
            )
            """,
            tenant_id,
            source,
            source_id,
        )
    return bool(exists)


async def mark_seen(payload: dict) -> uuid.UUID | None:
    """
    Record the event in the ledger / raw store (encrypted).

    Returns raw_events.id, or None if already present (unique conflict).
    """
    raw_event_id = await store_raw_event(payload)
    if raw_event_id is None:
        log.info(
            "mark_seen conflict (already present): source=%s source_id=%s",
            payload.get("source"),
            payload.get("source_id"),
        )
        return None

    log.info(
        "mark_seen stored raw_event_id=%s source=%s source_id=%s",
        raw_event_id,
        payload.get("source"),
        payload.get("source_id"),
    )
    return raw_event_id
