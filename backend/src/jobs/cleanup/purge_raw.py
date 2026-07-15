"""
Manual / cron entry: purge expired raw_events (expires_at < now()).

Usage (from backend/ with venv + PYTHONPATH=src):
  python -m jobs.cleanup.purge_raw
"""
from __future__ import annotations

import asyncio
import logging

import asyncpg

from common.config.database_config import get_database_config
from database.pool import init_db_pool
from modules.ingestion.raw_events.store import purge_expired_raw_events

log = logging.getLogger(__name__)


async def run_purge_job() -> None:
    """Thin wrapper called by APScheduler or CLI."""
    log.info("[cron] raw-event purge job started")
    deleted = await purge_expired_raw_events()
    log.info("[cron] raw-event purge job complete - %d records deleted", deleted)


async def _main() -> None:
    config = get_database_config()
    if not config.dsn:
        raise RuntimeError("DATABASE_URL is not set — check backend/.env")

    pool = await asyncpg.create_pool(
        dsn=config.dsn,
        min_size=1,
        max_size=2,
        statement_cache_size=0,
    )
    await init_db_pool(pool)
    try:
        await run_purge_job()
    finally:
        await pool.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(_main())
