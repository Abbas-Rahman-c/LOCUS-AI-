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

Transaction correction: `set_config(name, value, is_local=true)` only stays
in effect for "the current transaction." Without an explicit transaction
open, each statement asyncpg sends is its own implicit one-statement
transaction — meaning the GUC set here would revert before the caller's
*next, separate* query ever ran, silently defeating RLS (fail-closed: every
tenant_id predicate would compare against an empty setting and match
nothing, not leak across tenants, but retrieval would incorrectly return
zero rows for everyone). Wrapping the whole context in `conn.transaction()`
keeps the setting active for every statement the caller runs before this
context exits, and commits/rolls back atomically with them.

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
    Acquire a pooled connection, open a transaction, and set
    app.current_tenant_id for the duration of this context.

    The transaction is opened BEFORE set_config() runs, so is_local=true
    binds to it correctly; every query the caller executes while inside
    this context (including further explicit `conn.transaction()` blocks,
    which asyncpg automatically nests as savepoints) shares that same
    transaction and sees the same tenant setting. The transaction commits
    on clean exit or rolls back on exception; the connection is always
    released back to the pool afterward either way.
    """
    tenant_str = str(tenant_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # set_config(param, value, is_local=true) — scoped to this
            # transaction, which is now open for the whole yielded block.
            await conn.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)",
                tenant_str,
            )
            yield conn
