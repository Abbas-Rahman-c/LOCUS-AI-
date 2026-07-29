"""
Worker runner entry point - starts all registered consumer workers and the
in-process APScheduler (Monday Team Pulse + daily raw purge).

Each worker polls its own pgmq queue. Workers are co-located here;
business logic stays in the respective modules/.

Scheduler note: APScheduler is started once in this process (not in the
FastAPI API lifespan) so multi-replica API deploys do not fire duplicate
Monday digest jobs. Production hardening later: Cloud Scheduler -> HTTP
into the same run_digest_job entrypoint.
"""
from __future__ import annotations

import asyncio
import logging

import asyncpg

from common.config.database_config import get_admin_database_config, get_app_database_config

log = logging.getLogger(__name__)


async def start_all_workers() -> None:
    """Launch all queue workers concurrently."""
    from queues.workers.embedding_worker import run_embedding_worker
    from queues.workers.event_worker import run_event_worker

    log.info("Starting all queue workers...")
    await asyncio.gather(
        run_event_worker(),
        run_embedding_worker(),
        # Add digest_queue worker here only if fan-out moves off sync cron
    )


async def _main() -> None:
    config = get_app_database_config()
    if not config.dsn:
        raise RuntimeError("APP_DATABASE_URL is not set — check backend/.env")

    admin_config = get_admin_database_config()
    if not admin_config.dsn:
        raise RuntimeError("DATABASE_URL is not set — check backend/.env")

    log.info("Creating asyncpg pools for workers...")
    pool = await asyncpg.create_pool(
        dsn=config.dsn,
        min_size=config.min_size,
        max_size=config.max_size,
        statement_cache_size=0,
    )
    admin_pool = await asyncpg.create_pool(
        dsn=admin_config.dsn,
        min_size=1,
        max_size=admin_config.max_size,
        statement_cache_size=0,
    )

    from database.pool import init_admin_db_pool, init_db_pool
    from jobs.scheduler.base import build_scheduler
    from queues.pgmq.client import init_pgmq_client

    await init_db_pool(pool)
    await init_admin_db_pool(admin_pool)
    await init_pgmq_client(pool)
    log.info("DB pools + pgmq client initialised")

    scheduler = build_scheduler()
    scheduler.start()
    log.info(
        "APScheduler started (jobs=%s)",
        [j.id for j in scheduler.get_jobs()],
    )

    try:
        await start_all_workers()
    finally:
        log.info("Shutting down APScheduler...")
        scheduler.shutdown(wait=False)
        log.info("Closing asyncpg pools...")
        await pool.close()
        await admin_pool.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(_main())
