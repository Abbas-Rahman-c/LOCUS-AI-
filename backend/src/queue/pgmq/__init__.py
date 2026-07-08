"""
pgmq package — the single canonical home for all Postgres-native queue infrastructure.
One client construction. All producers and workers import from here.
"""
from queue.pgmq.client import PgmqClient, get_pgmq_client, init_pgmq_client
from queue.pgmq.queues import QueueName

__all__ = ["PgmqClient", "get_pgmq_client", "init_pgmq_client", "QueueName"]
