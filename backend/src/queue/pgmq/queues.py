"""
Queue name constants — the canonical list of pgmq queues in the system.
Import these wherever a queue name is needed; never hardcode a string.
"""
from enum import StrEnum


class QueueName(StrEnum):
    INGESTION  = "ingestion_queue"   # Raw EventEnvelope ? AI pipeline
    EMBEDDING  = "embedding_queue"   # Post-extraction embedding jobs
    DIGEST     = "digest_queue"      # Weekly digest generation jobs
