"""
Ingestion producer - enqueues normalised EventEnvelopes into the ingestion queue.

This is the canonical location for connectors to enqueue shaped events.
"""
from __future__ import annotations

from pgmq.client import get_pgmq_client
from pgmq.queues import QueueName


async def enqueue_event(envelope: dict) -> int:
    """Enqueue a normalised EventEnvelope for async AI processing."""
    client = get_pgmq_client()
    return await client.send(QueueName.INGESTION, envelope)


async def enqueue_embedding_job(capture_id: str, summary: str) -> int:
    """Enqueue a post-extraction embedding job."""
    client = get_pgmq_client()
    return await client.send(QueueName.EMBEDDING, {"capture_id": capture_id, "summary": summary})