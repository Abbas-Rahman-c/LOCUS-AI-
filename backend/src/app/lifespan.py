"""
Application lifespan context manager.
Handles startup (DB pools, queue connections) and shutdown teardown.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from common.config.database_config import get_admin_database_config, get_app_database_config

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_app_database_config()
    if not config.dsn:
        raise RuntimeError("APP_DATABASE_URL is not set - check backend/.env")

    admin_config = get_admin_database_config()
    if not admin_config.dsn:
        raise RuntimeError("DATABASE_URL is not set - check backend/.env")

    log.info("Creating asyncpg pools...")
    pool = None
    admin_pool = None
    try:
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
        app.state.db_pool = pool
        app.state.admin_db_pool = admin_pool

        from database.pool import init_admin_db_pool, init_db_pool
        from queues.pgmq.client import init_pgmq_client

        await init_db_pool(pool)
        await init_admin_db_pool(admin_pool)
        await init_pgmq_client(pool)
        log.info("DB pools + pgmq client initialised")
    except Exception as e:
        log.error(f"Failed to connect to the database: {e}")
        log.warning("App starting without database connection. Features relying on DB will fail.")

    try:
        yield
    finally:
        from modules.ai.embeddings.provider import close_voyage_session

        log.info("Closing Voyage HTTP session...")
        await close_voyage_session()
        if pool is not None:
            log.info("Closing asyncpg pools...")
            await pool.close()
        if admin_pool is not None:
            await admin_pool.close()

