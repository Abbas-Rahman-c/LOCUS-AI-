"""
Shared asyncpg pool singletons.

Two separate pools exist on purpose:
  - The default pool (get_db_pool) uses APP_DATABASE_URL (locus_app role),
    RLS-bound. Almost everything should use this.
  - The admin pool (get_admin_db_pool) uses DATABASE_URL (postgres role),
    bypasses RLS. Reserved for the narrow set of operations that must run
    BEFORE a tenant is known — most notably, looking up which tenant a
    freshly-authenticated user belongs to during session creation. Using
    the RLS-bound pool for that lookup is a chicken-and-egg bug: RLS
    requires app.current_tenant_id to already be set, but this lookup's
    entire job is determining what that tenant_id should be.
"""
from __future__ import annotations

import asyncpg

_pool: asyncpg.Pool | None = None
_admin_pool: asyncpg.Pool | None = None


async def init_db_pool(pool: asyncpg.Pool) -> None:
    """Register the shared, RLS-bound pool (called at startup)."""
    global _pool
    _pool = pool


def get_db_pool() -> asyncpg.Pool:
    """Return the shared, RLS-bound pool. Raises if not initialised."""
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_db_pool() at startup")
    return _pool


async def init_admin_db_pool(pool: asyncpg.Pool) -> None:
    """Register the admin, RLS-bypassing pool (called at startup)."""
    global _admin_pool
    _admin_pool = pool


def get_admin_db_pool() -> asyncpg.Pool:
    """Return the admin pool. Use only for pre-tenant-context lookups."""
    if _admin_pool is None:
        raise RuntimeError("Admin DB pool not initialised — call init_admin_db_pool() at startup")
    return _admin_pool