"""
Ingestion producer - enqueues normalised EventEnvelopes and embedding jobs
into their respective pgmq queues.

Moved from modules/ingestion/queue/ - this is the canonical location.
Imports the shared client from queues.pgmq.client; never instantiates its own connection.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import ValidationError

from modules.ingestion.envelope.schemas import EventEnvelope
from queues.pgmq.client import get_pgmq_client
from queues.pgmq.queues import QueueName
from queues.pgmq.schemas import EmbeddingJob


class EmbeddingEnqueueError(Exception):
    """Raised when an embedding job fails validation or fails to reach pgmq."""


class EventEnqueueError(Exception):
    """Raised when an ingestion event fails EventEnvelope validation or fails to reach pgmq."""


async def enqueue_event(envelope: dict) -> int:
    """Validate and enqueue a normalised EventEnvelope for async AI processing.

    Validating here - not just in the ingestion worker that reads the
    message back - means every connector shares the exact same contract at
    send time instead of discovering a shape mismatch only once a message
    is already on the queue.

    Args:
        envelope: dict with EventEnvelope's fields (tenant_id, source,
            source_id, actor, thread_ref, permission_scope, raw_content,
            received_at).
    Returns:
        pgmq message ID

    Raises:
        EventEnqueueError: the payload fails EventEnvelope validation, or
            pgmq.send() fails. Callers decide whether/how to react - the
            Slack webhook handler logs and skips rather than raising further,
            since Slack must still get its 200 ack.
    """
    try:
        event = EventEnvelope.model_validate(envelope)
    except ValidationError as exc:
        raise EventEnqueueError(f"Invalid EventEnvelope payload: {exc}") from exc

    client = get_pgmq_client()
    try:
        return await client.send(QueueName.INGESTION, event.model_dump(mode="json"))
    except Exception as exc:
        raise EventEnqueueError(f"Failed to enqueue event: {exc}") from exc


async def enqueue_embedding_job(*, tenant_id: UUID, decision_id: UUID) -> int:
    """Enqueue a post-persistence embedding job for one decision.

    The job carries only tenant_id and decision_id - the embedding worker
    fetches the persisted decision from PostgreSQL itself, so no decision
    content ever crosses the queue (or gets logged here). Raises
    EmbeddingEnqueueError if the payload fails validation or pgmq.send()
    fails; callers decide whether/how to react.
    """
    try:
        job = EmbeddingJob(tenant_id=tenant_id, decision_id=decision_id)
    except ValidationError as exc:
        raise EmbeddingEnqueueError(f"Invalid embedding job payload: {exc}") from exc

    client = get_pgmq_client()
    try:
        return await client.send(QueueName.EMBEDDING, job.model_dump(mode="json"))
    except Exception as exc:
        raise EmbeddingEnqueueError(f"Failed to enqueue embedding job: {exc}") from exc
