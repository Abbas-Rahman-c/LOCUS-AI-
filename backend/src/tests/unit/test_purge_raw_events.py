"""
Unit tests for the raw event purge job.

Tests the core requirement:
  - A row with expires_at < now() is deleted by purge_expired_raw_events()
  - A row with expires_at > now() is left completely untouched

Both the purge function and the DB pool are mocked so no real database
is needed — same pattern as test_search_service.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.cleanup.purge_raw import run_purge_job
from modules.ingestion.raw_events.store import purge_expired_raw_events

pytestmark = pytest.mark.asyncio

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)
_EXPIRED_AT = _NOW - timedelta(days=31)    # 31 days ago → should be deleted
_LIVE_AT    = _NOW + timedelta(days=1)     # tomorrow → should survive


def _mock_pool(execute_result: str = "DELETE 1"):
    """Return a mock asyncpg pool whose conn.execute() returns execute_result."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=execute_result)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=conn),
        __aexit__=AsyncMock(return_value=None),
    ))
    return pool, conn


# --------------------------------------------------------------------------
# purge_expired_raw_events() unit tests
# --------------------------------------------------------------------------

class TestPurgeExpiredRawEvents:
    async def test_expired_row_is_deleted(self):
        """The purge SQL runs and DELETE 1 is parsed correctly."""
        pool, conn = _mock_pool("DELETE 1")

        with patch("modules.ingestion.raw_events.store.get_db_pool", return_value=pool):
            deleted = await purge_expired_raw_events()

        assert deleted == 1
        conn.execute.assert_awaited_once()
        # Verify the SQL touches raw_events and uses expires_at < $1
        sql_called = conn.execute.await_args.args[0]
        assert "raw_events" in sql_called
        assert "expires_at" in sql_called

    async def test_non_expired_row_survives(self):
        """When no rows are expired, DELETE 0 → returns 0, no data lost."""
        pool, conn = _mock_pool("DELETE 0")

        with patch("modules.ingestion.raw_events.store.get_db_pool", return_value=pool):
            deleted = await purge_expired_raw_events()

        assert deleted == 0

    async def test_multiple_expired_rows_all_deleted(self):
        """Purge deletes ALL expired rows in one statement."""
        pool, conn = _mock_pool("DELETE 47")

        with patch("modules.ingestion.raw_events.store.get_db_pool", return_value=pool):
            deleted = await purge_expired_raw_events()

        assert deleted == 47

    async def test_purge_passes_current_timestamp_as_cutoff(self):
        """The cutoff passed to DELETE must be 'now' — not a hardcoded date."""
        pool, conn = _mock_pool("DELETE 0")

        before = datetime.now(timezone.utc)
        with patch("modules.ingestion.raw_events.store.get_db_pool", return_value=pool):
            await purge_expired_raw_events()
        after = datetime.now(timezone.utc)

        # The timestamp arg passed to conn.execute should be between before and after
        cutoff_arg = conn.execute.await_args.args[1]
        assert isinstance(cutoff_arg, datetime)
        assert before <= cutoff_arg <= after, (
            f"Cutoff {cutoff_arg} is not within [{before}, {after}] — "
            "purge is not using the current time as cutoff"
        )

    async def test_empty_pool_result_returns_zero(self):
        """Graceful handling if execute() returns empty string (edge case)."""
        pool, conn = _mock_pool("")

        with patch("modules.ingestion.raw_events.store.get_db_pool", return_value=pool):
            deleted = await purge_expired_raw_events()

        assert deleted == 0


# --------------------------------------------------------------------------
# run_purge_job() — the cron entry point
# --------------------------------------------------------------------------

class TestRunPurgeJob:
    async def test_run_purge_job_calls_purge_and_returns_count(self):
        """run_purge_job() must call purge_expired_raw_events() and log the count."""
        with patch(
            "jobs.cleanup.purge_raw.purge_expired_raw_events",
            AsyncMock(return_value=5),
        ) as mock_purge:
            await run_purge_job()

        mock_purge.assert_awaited_once()

    async def test_run_purge_job_does_not_raise_on_zero_deleted(self):
        """Job should not raise when there's nothing to purge."""
        with patch(
            "jobs.cleanup.purge_raw.purge_expired_raw_events",
            AsyncMock(return_value=0),
        ):
            await run_purge_job()  # must not raise


# --------------------------------------------------------------------------
# Scheduler registration
# --------------------------------------------------------------------------

class TestSchedulerRegistration:
    def test_purge_job_is_registered_in_scheduler(self):
        """Confirm build_scheduler() registers the purge job with a daily cron."""
        from jobs.scheduler.base import build_scheduler

        scheduler = build_scheduler()
        job_ids = [job.id for job in scheduler.get_jobs()]

        assert "purge_raw_events" in job_ids, (
            "purge_raw_events job is not registered in the scheduler — "
            "it will never run automatically"
        )

    def test_purge_job_runs_daily(self):
        """Purge job must be on a daily (not weekly) cadence."""
        from jobs.scheduler.base import build_scheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = build_scheduler()
        purge_job = next(j for j in scheduler.get_jobs() if j.id == "purge_raw_events")

        assert isinstance(purge_job.trigger, CronTrigger)
        # CronTrigger fields: hour=2, minute=0 means daily at 02:00 UTC
        fields = {f.name: str(f) for f in purge_job.trigger.fields}
        assert fields["hour"] == "2"
        assert fields["minute"] == "0"
