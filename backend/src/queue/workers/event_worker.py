"""
Ingestion event worker - polls the ingestion queue and dispatches each event.

Step 3 (current): dedup ledger via public.raw_events, then log.
Later steps: chunk → AI pipeline → decisions store.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from queue.pgmq.client import get_pgmq_client
from queue.pgmq.queues import QueueName

log = logging.getLogger(__name__)

VISIBILITY_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 2


async def run_event_worker() -> None:
    """Long-running worker loop: read → process → delete from ingestion queue."""
    client = get_pgmq_client()
    log.info("Event worker started - polling %s", QueueName.INGESTION)

    while True:
        messages = await client.read(
            QueueName.INGESTION, vt=VISIBILITY_TIMEOUT_SECONDS, batch=5
        )
        for msg in messages:
            msg_id = msg["msg_id"]
            try:
                await _process_message(_normalize_payload(msg["message"]))
                await client.delete(QueueName.INGESTION, msg_id)
                log.info("Processed and deleted msg_id=%s", msg_id)
            except Exception:
                log.exception(
                    "Failed to process msg_id=%s - will retry after VT expires", msg_id
                )
        if not messages:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


def _normalize_payload(raw: Any) -> dict:
    """pgmq may return message as dict or JSON string depending on driver/version."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, (bytes, bytearray)):
        return json.loads(raw.decode("utf-8"))
    raise TypeError(f"Unexpected message type: {type(raw)!r}")


async def _process_message(payload: dict) -> None:
    """
    Step 3: dedup → mark_seen (raw_events) → log.

    TODO (later): chunk → run_pipeline → store decision
    """
    from modules.ingestion.dedup.ledger import is_duplicate, mark_seen

    log.info(
        "Received event: tenant_id=%s source=%s source_id=%s event_type=%s",
        payload.get("tenant_id"),
        payload.get("source"),
        payload.get("source_id"),
        payload.get("event_type"),
    )

    if await is_duplicate(payload):
        log.info(
            "Duplicate skipped: source=%s source_id=%s",
            payload.get("source"),
            payload.get("source_id"),
        )
        return

    raw_event_id = await mark_seen(payload)
    if raw_event_id is None:
        log.info(
            "Duplicate on insert (race): source=%s source_id=%s",
            payload.get("source"),
            payload.get("source_id"),
        )
        return

    log.info("Accepted new event raw_event_id=%s", raw_event_id)
    log.debug("Full payload: %s", payload)
