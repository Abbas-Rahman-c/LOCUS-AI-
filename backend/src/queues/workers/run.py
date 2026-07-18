"""
Worker runner entry point - starts all registered consumer workers.
Each worker polls its own pgmq queue. Workers are co-located here;
business logic stays in the respective modules/.
"""
from __future__ import annotations

import asyncio
import logging

import asyncpg

from common.config.database_config import get_app_database_config

log = logging.getLogger(__name__)


async def start_all_workers() -> None:
    """Launch all queue workers concurrently."""
    from queues.workers.event_worker import run_event_worker

    log.info("Starting all queue workers...")
    await asyncio.gather(
        run_event_worker(),
        # Add embedding_worker, digest_worker here as they are built
    )


async def _main() -> None:
    config = get_app_database_config()
    if not config.dsn:
        raise RuntimeError("APP_DATABASE_URL is not set — check backend/.env")

    log.info("Creating asyncpg pool for workers...")
    pool = await asyncpg.create_pool(
        dsn=config.dsn,
        min_size=config.min_size,
        max_size=config.max_size,
        statement_cache_size=0,
    )

    from database.pool import init_db_pool
    from queues.pgmq.client import init_pgmq_client

    await init_db_pool(pool)
    await init_pgmq_client(pool)
    log.info("DB pool + pgmq client initialised")

    try:
        await start_all_workers()
    finally:
        log.info("Closing asyncpg pool...")
        await pool.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(_main())
