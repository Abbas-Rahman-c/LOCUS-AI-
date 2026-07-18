"""
Tenant session context for row-level security.

Sets Postgres Grand Unified Configuration (GUC) `app.current_tenant_id`
on a connection so `tenant_isolation_*` policies can match rows.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from common.config.database_config import get_admin_database_config
from database.pool import get_db_pool


async def set_current_tenant_id(
    conn: asyncpg.Connection, tenant_id: uuid.UUID | str
) -> None:
    """Bind this connection to a tenant for the current transaction (is_local=true)."""
    await conn.execute(
        "select set_config('app.current_tenant_id', $1, true)",
        str(tenant_id),
    )


@asynccontextmanager
async def tenant_connection(
    tenant_id: uuid.UUID | str,
) -> AsyncIterator[asyncpg.Connection]:
    """
    Acquire a pool connection and set app.current_tenant_id for this transaction.

    Prefer this over bare pool.acquire() for any tenant-scoped query on the
    non-bypass APP_DATABASE_URL role.
    """
    pool = get_db_pool()
    async with pool.acquire() as conn:
        await set_current_tenant_id(conn, tenant_id)
        yield conn


@asynccontextmanager
async def admin_connection() -> AsyncIterator[asyncpg.Connection]:
    """
    Short-lived connection as DATABASE_URL (postgres / bypass).

    Use only for cross-tenant admin work (e.g. resolve tenant by email,
    list connections for cron). Prefer tenant_connection once tenant_id is known.
    """
    config = get_admin_database_config()
    if not config.dsn:
        raise RuntimeError("DATABASE_URL is not set — check backend/.env")
    conn = await asyncpg.connect(config.dsn, statement_cache_size=0)
    try:
        yield conn
    finally:
        await conn.close()
