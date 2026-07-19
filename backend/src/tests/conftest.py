"""
Shared pytest fixtures for the Locus AI test suite.

Provides:
  - mock_pool: an asyncpg.Pool double with pre-wired rows
  - make_tenant_jwt / decode_tenant_jwt: JWT helpers for auth tests
  - make_tenant_ctx: TenantContext factory
  - env_secret: monkeypatches APP_SECRET_KEY for all tests that sign JWTs
"""
from __future__ import annotations

import sys
import os

# Put src at the absolute front of sys.path so our local queue package takes precedence over stdlib queue
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import uuid
from unittest.mock import AsyncMock, MagicMock


import pytest

from app.dependencies import TenantContext
from modules.auth.service import issue_tenant_jwt

TEST_SECRET = "test-secret-key-for-unit-tests-must-be-at-least-32-chars-long"

# ── Environment ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def env_secret(monkeypatch):
    """Ensures APP_SECRET_KEY is set for every test."""
    monkeypatch.setenv("APP_SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("RAW_EVENTS_ENCRYPTION_KEY", TEST_SECRET)


# ── Tenant helpers ─────────────────────────────────────────────────────────────


def make_tenant_ctx(
    tenant_id: uuid.UUID | None = None,
    user_id: str | None = None,
    role: str = "owner",
) -> TenantContext:
    return TenantContext(
        user_id=user_id or str(uuid.uuid4()),
        tenant_id=str(tenant_id or uuid.uuid4()),
        role=role,
    )


def make_tenant_jwt(
    tenant_id: uuid.UUID | str,
    user_id: str | None = None,
    role: str = "owner",
) -> str:
    return issue_tenant_jwt(
        user_id=user_id or str(uuid.uuid4()),
        tenant_id=str(tenant_id),
        role=role,
    )


# ── Mock DB pool ───────────────────────────────────────────────────────────────


def _make_conn_mock(rows: list[dict] | None = None, scalar: int = 0):
    """Return an asyncpg.Connection-shaped mock that returns canned data."""
    conn = AsyncMock()

    # set_config — used by tenant_conn to set app.current_tenant_id
    conn.execute = AsyncMock(return_value="SET")

    if rows is not None:
        record_rows = [_dict_to_record(r) for r in rows]
        conn.fetch = AsyncMock(return_value=record_rows)
        conn.fetchrow = AsyncMock(return_value=record_rows[0] if record_rows else None)
        conn.fetchval = AsyncMock(return_value=scalar or len(rows))
    else:
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetchval = AsyncMock(return_value=0)

    return conn


def _dict_to_record(d: dict):
    """Wrap a plain dict so it supports both dict and attribute access (like asyncpg Record)."""
    record = MagicMock()
    record.__getitem__ = lambda self, key: d[key]
    record.keys = lambda: d.keys()
    record.items = lambda: d.items()
    record.__iter__ = lambda self: iter(d)
    # Also expose as attributes for row["field"] pattern
    for k, v in d.items():
        setattr(record, k, v)
    return record


@pytest.fixture
def mock_pool():
    """An asyncpg.Pool mock whose acquire() yields a configurable connection."""
    pool = MagicMock()
    conn = _make_conn_mock()

    class _AcquireCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *_):
            pass

    pool.acquire = MagicMock(return_value=_AcquireCtx())
    pool._conn = conn  # expose for per-test customisation
    return pool


def make_pool_with_rows(rows: list[dict], scalar: int = 0):
    """Return a mock pool pre-wired with specific rows."""
    pool = MagicMock()
    conn = _make_conn_mock(rows=rows, scalar=scalar)

    class _AcquireCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *_):
            pass

    pool.acquire = MagicMock(return_value=_AcquireCtx())
    pool._conn = conn
    return pool
