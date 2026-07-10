"""
pgmq client - THE single pgmq connection point in the codebase.

All modules that need to enqueue or consume messages must import from here.
Do NOT instantiate a pgmq connection anywhere else in src/.
"""
from __future__ import annotations

import asyncpg

from pgmq.queues import QueueName


class PgmqClient:
    """Thin async wrapper around raw asyncpg for pgmq send/read/delete."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def send(self, queue: QueueName, message: dict) -> int:
        """Enqueue a message. Returns the message ID."""
        import json

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT pgmq.send($1, $2::jsonb)", queue.value, json.dumps(message)
            )
            return row[0]

    async def read(self, queue: QueueName, vt: int = 30, batch: int = 1) -> list[dict]:
        """Read up to `batch` messages with visibility timeout `vt` seconds."""
        import json

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM pgmq.read($1, $2, $3)", queue.value, vt, batch
            )
            results = []
            for r in rows:
                d = dict(r)
                if isinstance(d.get("message"), str):
                    try:
                        d["message"] = json.loads(d["message"])
                    except Exception:
                        pass
                results.append(d)
            return results

    async def delete(self, queue: QueueName, msg_id: int) -> None:
        """Permanently delete a processed message."""
        async with self._pool.acquire() as conn:
            await conn.execute("SELECT pgmq.delete($1::text, $2::bigint)", queue.value, msg_id)


_client: PgmqClient | None = None


def get_pgmq_client() -> PgmqClient:
    """Return the shared pgmq client. Must be initialised via init_pgmq_client() at startup."""
    if _client is None:
        raise RuntimeError("pgmq client not initialised - call init_pgmq_client() in lifespan")
    return _client


async def init_pgmq_client(pool: asyncpg.Pool) -> None:
    """Initialise the singleton client from the shared DB pool (called in app lifespan)."""
    global _client
    _client = PgmqClient(pool)