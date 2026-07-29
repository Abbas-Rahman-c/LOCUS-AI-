"""
Unit tests for jobs.cron.digest_cron.run_digest_job tenant fan-out.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from modules.digest.schemas import DigestItem, DigestMetadata, DigestResponse

pytestmark = pytest.mark.asyncio

TENANT_A = uuid4()
TENANT_B = uuid4()
USER_A = uuid4()


def _digest(scope: str = "team") -> DigestResponse:
    return DigestResponse(
        scope=scope,  # type: ignore[arg-type]
        period="2026-07-13/2026-07-20",
        summary="Week summary",
        items=[
            DigestItem(
                decision_statement="Ship Team Pulse",
                rationale=None,
                confidence=0.9,
                created_at=None,
            )
        ],
        metadata=DigestMetadata(
            model="m",
            latency_ms=1.0,
            decision_count=1,
            token_estimate=10,
            personalized=scope == "team",
        ),
    )


class TestRunDigestJob:
    async def test_fans_out_team_and_personal_per_tenant(self):
        generate = AsyncMock(side_effect=lambda *a, **k: _digest(k.get("scope", a[3] if len(a) > 3 else "team")))
        save = AsyncMock()
        list_tenants = AsyncMock(return_value=[TENANT_A, TENANT_B])
        list_members = AsyncMock(side_effect=[[USER_A], []])

        with (
            patch("jobs.cron.digest_cron.get_db_pool", return_value=object()),
            patch("jobs.cron.digest_cron._list_active_tenants", list_tenants),
            patch("jobs.cron.digest_cron._list_tenant_members", list_members),
            patch("jobs.cron.digest_cron.generate_team_pulse", generate),
            patch("jobs.cron.digest_cron.save_weekly_digest", save),
            patch("jobs.cron.digest_cron.digest_week_of", return_value=date(2026, 7, 20)),
        ):
            from jobs.cron.digest_cron import run_digest_job

            await run_digest_job()

        # Tenant A: team + personal; Tenant B: team only
        assert generate.await_count == 3
        assert save.await_count == 3

        team_calls = [
            c for c in generate.await_args_list if c.kwargs.get("scope") == "team" or (
                len(c.args) > 3 and c.args[3] == "team"
            )
        ]
        # generate_team_pulse(pool, tenant_id, scopes, scope=..., user_id=...)
        scopes = []
        for c in generate.await_args_list:
            if "scope" in c.kwargs:
                scopes.append(c.kwargs["scope"])
            elif len(c.args) > 3:
                scopes.append(c.args[3])
        assert scopes.count("team") == 2
        assert scopes.count("personal") == 1

    async def test_continues_after_one_tenant_failure(self):
        async def generate_side_effect(pool, tenant_id, permission_scopes=None, scope="team", user_id=None, **_):
            if tenant_id == TENANT_A and scope == "team":
                raise RuntimeError("boom")
            return _digest(scope)

        generate = AsyncMock(side_effect=generate_side_effect)
        save = AsyncMock()

        with (
            patch("jobs.cron.digest_cron.get_db_pool", return_value=object()),
            patch(
                "jobs.cron.digest_cron._list_active_tenants",
                AsyncMock(return_value=[TENANT_A, TENANT_B]),
            ),
            patch(
                "jobs.cron.digest_cron._list_tenant_members",
                AsyncMock(return_value=[]),
            ),
            patch("jobs.cron.digest_cron.generate_team_pulse", generate),
            patch("jobs.cron.digest_cron.save_weekly_digest", save),
            patch("jobs.cron.digest_cron.digest_week_of", return_value=date(2026, 7, 20)),
        ):
            from jobs.cron.digest_cron import run_digest_job

            await run_digest_job()

        # Tenant A team failed; Tenant A members skipped after team... actually
        # members still run after team failure (we don't continue on team fail —
        # we log and then still list members). Tenant B team succeeds.
        assert save.await_count >= 1
        saved_tenants = {c.args[1] for c in save.await_args_list}
        assert TENANT_B in saved_tenants
