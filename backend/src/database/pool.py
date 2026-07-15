"""
Shared asyncpg pool singleton.

Initialised once at process startup (FastAPI lifespan or worker runner).
All modules that need DB access must use get_db_pool() — do not create
separate pools.
"""
from __future__ import annotations

import asyncpg

_pool: asyncpg.Pool | None = None


async def init_db_pool(pool: asyncpg.Pool) -> None:
    """Register the shared pool (called at startup)."""
    global _pool
    _pool = pool


def get_db_pool() -> asyncpg.Pool:
    """Return the shared pool. Raises if init_db_pool() was not called."""
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_db_pool() at startup")
    return _pool
