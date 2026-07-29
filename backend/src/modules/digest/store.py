"""
Persist and load weekly Team Pulse digests.

Monday cron writes rows; GET /digest reads the stored row for the current
week when present so the UI does not need to trigger Claude generation.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

import asyncpg

from database.tenant_connection import tenant_conn
from modules.digest.schemas import DigestItem, DigestMetadata, DigestResponse

log = logging.getLogger(__name__)


def digest_week_of(now: datetime | None = None) -> date:
    """Monday (UTC) that identifies the current digest week.

    The weekly job runs Monday 09:00 UTC. Before that hour on Monday, the
    previous Monday's digest is still the current one.
    """
    now = now or datetime.now(tz=timezone.utc)
    today = now.date()
    this_monday = today - timedelta(days=today.weekday())
    if today == this_monday and now.hour < 9:
        return this_monday - timedelta(days=7)
    return this_monday


def period_bounds_for_week(week_of: date) -> tuple[date, date]:
    """Rolling 7-day window ending on the delivery Monday (inclusive end)."""
    period_end = week_of
    period_start = week_of - timedelta(days=7)
    return period_start, period_end


def period_string(period_start: date, period_end: date) -> str:
    return f"{period_start.isoformat()}/{period_end.isoformat()}"


async def save_weekly_digest(
    pool: asyncpg.Pool,
    tenant_id: uuid.UUID | str,
    digest: DigestResponse,
    week_of: date,
    user_id: uuid.UUID | str | None = None,
) -> None:
    """Upsert a generated digest for the given tenant / scope / week."""
    period_start, period_end = period_bounds_for_week(week_of)
    try:
        start_s, end_s = digest.period.split("/", 1)
        period_start = date.fromisoformat(start_s)
        period_end = date.fromisoformat(end_s)
    except (ValueError, AttributeError):
        pass

    if digest.scope == "team":
        user_id = None
    elif user_id is None:
        raise ValueError("user_id is required when saving a personal digest")

    items_json = json.dumps([item.model_dump() for item in digest.items])
    metadata_json = json.dumps(digest.metadata.model_dump())

    async with tenant_conn(pool, tenant_id) as conn:
        if digest.scope == "team":
            await conn.execute(
                """
                INSERT INTO weekly_digests (
                    tenant_id, user_id, scope, week_of,
                    period_start, period_end, summary, items, metadata
                )
                VALUES ($1, NULL, 'team', $2, $3, $4, $5, $6::jsonb, $7::jsonb)
                ON CONFLICT (tenant_id, week_of) WHERE (scope = 'team')
                DO UPDATE SET
                    period_start = EXCLUDED.period_start,
                    period_end = EXCLUDED.period_end,
                    summary = EXCLUDED.summary,
                    items = EXCLUDED.items,
                    metadata = EXCLUDED.metadata,
                    created_at = now()
                """,
                tenant_id,
                week_of,
                period_start,
                period_end,
                digest.summary,
                items_json,
                metadata_json,
            )
        else:
            await conn.execute(
                """
                INSERT INTO weekly_digests (
                    tenant_id, user_id, scope, week_of,
                    period_start, period_end, summary, items, metadata
                )
                VALUES ($1, $2, 'personal', $3, $4, $5, $6, $7::jsonb, $8::jsonb)
                ON CONFLICT (tenant_id, user_id, week_of) WHERE (scope = 'personal')
                DO UPDATE SET
                    period_start = EXCLUDED.period_start,
                    period_end = EXCLUDED.period_end,
                    summary = EXCLUDED.summary,
                    items = EXCLUDED.items,
                    metadata = EXCLUDED.metadata,
                    created_at = now()
                """,
                tenant_id,
                user_id,
                week_of,
                period_start,
                period_end,
                digest.summary,
                items_json,
                metadata_json,
            )

    log.info(
        "Saved weekly digest tenant=%s scope=%s week_of=%s user_id=%s",
        tenant_id,
        digest.scope,
        week_of,
        user_id,
    )


async def load_weekly_digest(
    pool: asyncpg.Pool,
    tenant_id: uuid.UUID | str,
    scope: Literal["personal", "team"],
    week_of: date | None = None,
    user_id: uuid.UUID | str | None = None,
) -> DigestResponse | None:
    """Return the stored digest for this week, or None if not yet generated."""
    week_of = week_of or digest_week_of()

    if scope == "personal" and user_id is None:
        return None

    async with tenant_conn(pool, tenant_id) as conn:
        if scope == "team":
            row = await conn.fetchrow(
                """
                SELECT scope, period_start, period_end, summary, items, metadata
                FROM weekly_digests
                WHERE tenant_id = $1 AND scope = 'team' AND week_of = $2
                """,
                tenant_id,
                week_of,
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT scope, period_start, period_end, summary, items, metadata
                FROM weekly_digests
                WHERE tenant_id = $1 AND scope = 'personal'
                  AND user_id = $2 AND week_of = $3
                """,
                tenant_id,
                user_id,
                week_of,
            )

    if row is None:
        return None

    items_raw = row["items"]
    if isinstance(items_raw, str):
        items_raw = json.loads(items_raw)
    meta_raw = row["metadata"]
    if isinstance(meta_raw, str):
        meta_raw = json.loads(meta_raw)

    return DigestResponse(
        scope=row["scope"],
        period=period_string(row["period_start"], row["period_end"]),
        summary=row["summary"],
        items=[DigestItem.model_validate(i) for i in items_raw],
        metadata=DigestMetadata.model_validate(meta_raw),
    )
