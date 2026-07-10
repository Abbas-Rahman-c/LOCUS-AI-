"""
Application lifespan context manager.
Handles startup (DB pool, queue connections) and shutdown teardown.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from common.config.database_config import get_database_config

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_database_config()
    if not config.dsn:
        raise RuntimeError("DATABASE_URL is not set — check backend/.env")

    # Create pool BEFORE importing local `queue` package — that name shadows
    # the stdlib queue module used by asyncpg's ThreadPoolExecutor.
    log.info("Creating asyncpg pool...")
    pool = await asyncpg.create_pool(
        dsn=config.dsn,
        min_size=config.min_size,
        max_size=config.max_size,
        statement_cache_size=0,  # required for Supabase PgBouncer transaction mode
    )
    app.state.db_pool = pool

    from database.pool import init_db_pool
    from queue.pgmq.client import init_pgmq_client

    await init_db_pool(pool)
    await init_pgmq_client(pool)
    log.info("DB pool + pgmq client initialised")

    try:
        yield
    finally:
        log.info("Closing asyncpg pool...")
        await pool.close()
