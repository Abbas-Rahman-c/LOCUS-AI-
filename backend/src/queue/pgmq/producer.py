"""
Ingestion producer - enqueues normalised EventEnvelopes into the ingestion queue.

Moved from modules/ingestion/queue/ - this is the canonical location.
Imports the shared client from queue.pgmq.client; never instantiates its own connection.
"""
from __future__ import annotations
from queue.pgmq.client import get_pgmq_client
from queue.pgmq.queues import QueueName


async def enqueue_event(envelope: dict) -> int:
    """Enqueue a normalised EventEnvelope for async AI processing.
    
    Args:
        envelope: Serialised EventEnvelope dict (tenant_id, source, source_id, ...)
    Returns:
        pgmq message ID
    """
    client = get_pgmq_client()
    return await client.send(QueueName.INGESTION, envelope)


async def enqueue_embedding_job(capture_id: str, summary: str) -> int:
    """Enqueue a post-extraction embedding job."""
    client = get_pgmq_client()
    return await client.send(QueueName.EMBEDDING, {"capture_id": capture_id, "summary": summary})
