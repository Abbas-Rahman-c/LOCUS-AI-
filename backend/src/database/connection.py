"""
Shared database connection pool helper.
"""
from __future__ import annotations
import asyncpg

_pool: asyncpg.Pool | None = None


def get_db_pool() -> asyncpg.Pool:
    """Get the active database pool. Must be initialized via init_db_pool() first."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() in lifespan.")
    return _pool


def init_db_pool(pool: asyncpg.Pool) -> None:
    """Initialize the global database pool."""
    global _pool
    _pool = pool
