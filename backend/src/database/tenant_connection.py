"""
Tenant-scoped database connection helper (Layer 1 of 2 for tenant isolation).

Every request handler that touches tenant data MUST use this context manager
instead of acquiring from the pool directly.  It sets the Postgres session
variable `app.current_tenant_id` so that all RLS policies fire correctly for
the duration of the connection.

Layer 1: RLS policies (database-level).
Layer 2: assert_tenant_scope() in modules/security/tenant_guard.py
         (application-level pre-filter called after every DB fetch).

A failure in one layer alone cannot expose another tenant's data.

Usage:
    from database.tenant_connection import tenant_conn

    async with tenant_conn(pool, tenant_id) as conn:
        rows = await conn.fetch("SELECT * FROM decisions")
        for row in rows:
            assert_tenant_scope(row["tenant_id"], tenant_id)   # Layer 2
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg


@asynccontextmanager
async def tenant_conn(
    pool: asyncpg.Pool,
    tenant_id: uuid.UUID | str,
) -> AsyncIterator[asyncpg.Connection]:
    """
    Acquire a pooled connection and set app.current_tenant_id for the
    duration of this context.  The setting is scoped to the current
    transaction (true = local to transaction), so it clears automatically
    when the connection is returned to the pool.
    """
    tenant_str = str(tenant_id)

    async with pool.acquire() as conn:
        # set_config(param, value, is_local=true) — resets at transaction end
        await conn.execute(
            "SELECT set_config('app.current_tenant_id', $1, true)",
            tenant_str,
        )
        yield conn
