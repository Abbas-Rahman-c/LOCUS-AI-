"""
Canonical pgmq client package for the application.
"""
from __future__ import annotations

from pgmq.client import PgmqClient, get_pgmq_client, init_pgmq_client
from pgmq.queues import QueueName

__all__ = ["PgmqClient", "get_pgmq_client", "init_pgmq_client", "QueueName"]