"""
Ingestion event worker - polls the ingestion queue and dispatches each event
through the full AI pipeline.

Moved from modules/ingestion/workers/ - this is the canonical location.
Imports the shared pgmq client from queue.pgmq; does NOT create its own connection.
"""
from __future__ import annotations
import asyncio
import logging

from src.queue.pgmq.client import get_pgmq_client
from src.queue.pgmq.queues import QueueName

log = logging.getLogger(__name__)

VISIBILITY_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 2


async def run_event_worker() -> None:
    """Long-running worker loop: read ? dispatch ? delete from ingestion queue."""
    client = get_pgmq_client()
    log.info("Event worker started - polling %s", QueueName.INGESTION)

    while True:
        messages = await client.read(QueueName.INGESTION, vt=VISIBILITY_TIMEOUT_SECONDS, batch=5)
        for msg in messages:
            try:
                await _process_message(msg["message"])
                await client.delete(QueueName.INGESTION, msg["msg_id"])
            except Exception:
                log.exception("Failed to process msg_id=%s - will retry after VT expires", msg["msg_id"])
        if not messages:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _process_message(payload: dict) -> None:
    """Route a single EventEnvelope through dedup ? chunk ? AI pipeline ? store.
    
    Actual business logic lives in modules/; this is the dispatch layer only.
    """
    # Imports here to avoid circular deps at module load time
    from modules.ingestion.dedup.ledger import is_duplicate, mark_seen
    from modules.ingestion.chunking.chunker import chunk_envelope
    from modules.ai.pipeline.orchestrator import run_pipeline

    if await is_duplicate(payload):
        log.debug("Duplicate event skipped: source=%s id=%s", payload.get("source"), payload.get("source_id"))
        return

    await mark_seen(payload)
    chunks = await chunk_envelope(payload)
    for chunk in chunks:
        await run_pipeline(chunk)
