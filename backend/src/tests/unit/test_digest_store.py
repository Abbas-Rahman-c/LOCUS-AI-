"""
Unit tests for modules.digest.store period helpers and load mapping.
"""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from modules.digest.schemas import DigestItem, DigestMetadata, DigestResponse
from modules.digest.store import (
    digest_week_of,
    load_weekly_digest,
    period_bounds_for_week,
    period_string,
    save_weekly_digest,
)

pytestmark = pytest.mark.asyncio

TENANT = uuid4()


def _digest() -> DigestResponse:
    return DigestResponse(
        scope="team",
        period="2026-07-13/2026-07-20",
        summary="Summary",
        items=[
            DigestItem(
                decision_statement="Decide X",
                rationale=None,
                confidence=0.8,
                created_at=None,
            )
        ],
        metadata=DigestMetadata(
            model="m",
            latency_ms=2.0,
            decision_count=1,
            token_estimate=20,
            personalized=True,
        ),
    )


class TestPeriodHelpers:
    def test_period_bounds(self):
        start, end = period_bounds_for_week(date(2026, 7, 20))
        assert start == date(2026, 7, 13)
        assert end == date(2026, 7, 20)
        assert period_string(start, end) == "2026-07-13/2026-07-20"


class TestSaveWeeklyDigest:
    async def test_team_upsert_sql_executed(self):
        conn = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch("modules.digest.store.tenant_conn", return_value=cm):
            await save_weekly_digest(
                object(), TENANT, _digest(), date(2026, 7, 20)
            )

        assert conn.execute.await_count == 1
        sql = conn.execute.await_args.args[0]
        assert "scope = 'team'" in sql or "WHERE (scope = 'team')" in sql


class TestLoadWeeklyDigest:
    async def test_returns_none_when_no_row(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch("modules.digest.store.tenant_conn", return_value=cm):
            result = await load_weekly_digest(
                object(), TENANT, "team", week_of=date(2026, 7, 20)
            )

        assert result is None

    async def test_maps_row_to_digest_response(self):
        digest = _digest()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(
            return_value={
                "scope": "team",
                "period_start": date(2026, 7, 13),
                "period_end": date(2026, 7, 20),
                "summary": digest.summary,
                "items": [i.model_dump() for i in digest.items],
                "metadata": digest.metadata.model_dump(),
            }
        )
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch("modules.digest.store.tenant_conn", return_value=cm):
            result = await load_weekly_digest(
                object(), TENANT, "team", week_of=date(2026, 7, 20)
            )

        assert result is not None
        assert result.summary == "Summary"
        assert result.period == "2026-07-13/2026-07-20"
        assert len(result.items) == 1

    async def test_personal_requires_user_id(self):
        result = await load_weekly_digest(
            object(), TENANT, "personal", week_of=date(2026, 7, 20), user_id=None
        )
        assert result is None
