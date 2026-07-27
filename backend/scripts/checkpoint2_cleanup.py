"""
Checkpoint 2 cleanup — removes exactly the 5 dry-run records identified in
checkpoint2_manifest.json (by their real raw_event_id/decision_id, not a
wildcard), and verifies whole-tenant counts return to the pre-dry-run
baseline recorded in that same manifest.

Usage:
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/checkpoint2_cleanup.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import asyncpg
from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

from common.config.database_config import get_app_database_config
from database.pool import init_db_pool
from database.tenant_context import tenant_connection

CORPUS_DIR = SRC_DIR / "evaluation" / "corpus_v2"
TENANT_ID = uuid.UUID("13bcd0fa-1ed9-4634-93c7-278ba97ec658")


async def main() -> None:
    manifest = json.loads((CORPUS_DIR / "checkpoint2_manifest.json").read_text())
    baseline = manifest["baseline"]
    records = manifest["records"]
    decision_ids = [uuid.UUID(r["decision_id"]) for r in records]
    raw_event_ids = [uuid.UUID(r["raw_event_id"]) for r in records]

    print(f"Cleaning up exactly {len(records)} dry-run records:")
    for r in records:
        print(f"  {r['source_message_id']} decision_id={r['decision_id']} raw_event_id={r['raw_event_id']}")

    config = get_app_database_config()
    pool = await asyncpg.create_pool(dsn=config.dsn, min_size=1, max_size=5, statement_cache_size=0)
    await init_db_pool(pool)

    try:
        async with tenant_connection(TENANT_ID) as conn:
            async with conn.transaction():
                emb_deleted = await conn.fetch(
                    "delete from public.decision_embeddings where decision_id = any($1::uuid[]) and tenant_id=$2 returning decision_id",
                    decision_ids, TENANT_ID,
                )
                dec_deleted = await conn.fetch(
                    "delete from public.decisions where id = any($1::uuid[]) and tenant_id=$2 returning id",
                    decision_ids, TENANT_ID,
                )
                raw_deleted = await conn.fetch(
                    "delete from public.raw_events where id = any($1::uuid[]) and tenant_id=$2 returning id",
                    raw_event_ids, TENANT_ID,
                )

        print(f"\nDeleted: {len(emb_deleted)} embeddings, {len(dec_deleted)} decisions, {len(raw_deleted)} raw_events")

        async with tenant_connection(TENANT_ID) as conn:
            after = dict(await conn.fetchrow(
                """select
                     (select count(*) from public.raw_events where tenant_id=$1) as raw_events,
                     (select count(*) from public.decisions where tenant_id=$1) as decisions,
                     (select count(*) from public.decision_embeddings where tenant_id=$1) as embeddings""",
                TENANT_ID,
            ))

        print(f"\nWhole-tenant counts after cleanup: {after}")
        print(f"Baseline (pre-dry-run) counts:      {baseline}")
        matches = after == baseline
        print(f"Counts match pre-dry-run baseline exactly: {matches}")
        if not matches:
            raise RuntimeError(f"cleanup did not fully restore baseline: after={after} baseline={baseline}")

        # spot-check Stage 1 eval-* records untouched
        async with tenant_connection(TENANT_ID) as conn:
            stage1_count = await conn.fetchval(
                "select count(*) from public.raw_events where tenant_id=$1 and source_id like 'eval-%'",
                TENANT_ID,
            )
        print(f"Stage 1 ('eval-%') raw_events still present: {stage1_count} (expected 22)")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
