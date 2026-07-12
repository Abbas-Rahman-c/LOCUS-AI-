"""
Application lifespan context manager.
Handles startup (DB pool, queue connections) and shutdown teardown.
"""
from contextlib import asynccontextmanager
import os
import logging
from fastapi import FastAPI
import asyncpg
from dotenv import load_dotenv

from database.connection import init_db_pool
from src.queue.pgmq.client import init_pgmq_client

log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load environment variables
    load_dotenv()
    
    # Get database URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        log.error("DATABASE_URL env var is not set")
        raise RuntimeError("DATABASE_URL is required")
        
    # asyncpg doesn't support +asyncpg scheme prefix, strip if present
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        
    log.info("Connecting to database pool...")
    try:
        pool = await asyncpg.create_pool(db_url)
    except Exception as e:
        log.error(f"Failed to create database pool: {e}")
        raise
        
    app.state.pool = pool
    init_db_pool(pool)
    
    # Run database initialization schema
    log.info("Running database schema migrations...")
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "sql", "schema.sql")
    try:
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            async with pool.acquire() as conn:
                await conn.execute(schema_sql)
            log.info("Database schema initialized successfully")
        else:
            log.warning(f"schema.sql not found at {schema_path}")
    except Exception as e:
        log.error(f"Failed to run schema migrations: {e}")

    oauth_migration_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "database", "migrations", "001_gmail_oauth_tokens.sql"
    )
    try:
        with open(oauth_migration_path, "r", encoding="utf-8") as f:
            oauth_migration_sql = f.read()
        async with pool.acquire() as conn:
            await conn.execute(oauth_migration_sql)
        log.info("Gmail OAuth token storage verified")
    except Exception as e:
        log.error("Failed to initialize Gmail OAuth token storage: %s", e)
        
    # Try enabling PGMQ extension, otherwise use pgmq_fallback.sql
    log.info("Verifying PGMQ infrastructure...")
    try:
        async with pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pgmq CASCADE;")
        log.info("PGMQ extension verified successfully.")
    except Exception as ext_err:
        log.warning("PGMQ extension not available (%s). Trying table-based fallback...", ext_err)
        fallback_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "sql", "pgmq_fallback.sql")
        try:
            if os.path.exists(fallback_path):
                with open(fallback_path, "r", encoding="utf-8") as f:
                    fallback_sql = f.read()
                async with pool.acquire() as conn:
                    await conn.execute(fallback_sql)
                log.info("PGMQ table-based fallback schema initialized successfully.")
            else:
                log.error(f"PGMQ fallback schema file not found at {fallback_path}")
        except Exception as fb_err:
            log.error(f"Failed to initialize PGMQ fallback: {fb_err}")
        
    # Initialize pgmq client
    log.info("Initializing PGMQ client...")
    await init_pgmq_client(pool)
    
    # Auto-create standard queues (ingestion, embedding, digest)
    queues = ["ingestion_queue", "embedding_queue", "digest_queue"]
    for q in queues:
        try:
            async with pool.acquire() as conn:
                await conn.execute("SELECT pgmq.create($1);", q)
            log.info(f"PGMQ queue '{q}' successfully verified/created.")
        except Exception as q_err:
            log.debug(f"Queue '{q}' connection/creation skipped: {q_err}")

    yield
    
    # shutdown
    log.info("Closing database pool...")
    await pool.close()
