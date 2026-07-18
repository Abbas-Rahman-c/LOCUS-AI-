"""
Application lifespan context manager.
Handles startup (DB pool, queue connections) and shutdown teardown.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from common.config.database_config import get_app_database_config

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_app_database_config()
    if not config.dsn:
        raise RuntimeError("APP_DATABASE_URL is not set — check backend/.env")

    # Create pool BEFORE importing local `queue` package — that name shadows
    # the stdlib queue module used by asyncpg's ThreadPoolExecutor.
    log.info("Creating asyncpg pool...")
    try:
        pool = await asyncpg.create_pool(
            dsn=config.dsn,
            min_size=config.min_size,
            max_size=config.max_size,
            statement_cache_size=0,  # required for Supabase PgBouncer transaction mode
        )
        app.state.db_pool = pool

        from database.pool import init_db_pool
        from queues.pgmq.client import init_pgmq_client

        await init_db_pool(pool)
        await init_pgmq_client(pool)
        log.info("DB pool + pgmq client initialised")
    except Exception as e:
        log.error(f"Failed to connect to the database: {e}")
        log.warning("App starting without database connection. Features relying on DB will fail.")
        pool = None

    try:
        yield
    finally:
        if pool is not None:
            log.info("Closing asyncpg pool...")
            await pool.close()
