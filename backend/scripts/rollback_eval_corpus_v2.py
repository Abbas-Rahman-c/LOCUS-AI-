"""
CHECKPOINT 3 ARTIFACT — rollback script for the full eval2-* corpus load.

NOT executed automatically by load_eval_corpus_v2.py, and not run as part
of this checkpoint. Available on request, scoped strictly to source_id LIKE
'eval2-%' — never touches Stage 1's 'eval-%' records, the one pre-existing
real decision, or anything else.

Usage (only when explicitly requested):
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/rollback_eval_corpus_v2.py --confirm
"""
from __future__ import annotations

import asyncio
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

TENANT_ID = uuid.UUID("13bcd0fa-1ed9-4634-93c7-278ba97ec658")


async def main() -> None:
    if "--confirm" not in sys.argv:
        print("Dry-run mode (no --confirm passed). Showing what WOULD be deleted, deleting nothing.")

    config = get_app_database_config()
    pool = await asyncpg.create_pool(dsn=config.dsn, min_size=1, max_size=5, statement_cache_size=0)
    await init_db_pool(pool)

    try:
        async with tenant_connection(TENANT_ID) as conn:
            counts = dict(await conn.fetchrow(
                """select
                     (select count(*) from public.raw_events where tenant_id=$1 and source_id like 'eval2-%') as raw_events,
                     (select count(*) from public.decisions d join public.raw_events r on r.id = d.origin_raw_event_id
                        where d.tenant_id=$1 and r.source_id like 'eval2-%') as decisions,
                     (select count(*) from public.decision_embeddings e
                        join public.decisions d on d.id = e.decision_id
                        join public.raw_events r on r.id = d.origin_raw_event_id
                        where d.tenant_id=$1 and r.source_id like 'eval2-%') as embeddings""",
                TENANT_ID,
            ))
            print(f"eval2-* records currently in DB: {counts}")

            if "--confirm" in sys.argv:
                async with conn.transaction():
                    emb = await conn.fetch(
                        """delete from public.decision_embeddings where decision_id in (
                             select d.id from public.decisions d join public.raw_events r
                               on r.id = d.origin_raw_event_id
                             where d.tenant_id=$1 and r.source_id like 'eval2-%'
                           ) returning decision_id""",
                        TENANT_ID,
                    )
                    dec = await conn.fetch(
                        """delete from public.decisions where id in (
                             select d.id from public.decisions d join public.raw_events r
                               on r.id = d.origin_raw_event_id
                             where d.tenant_id=$1 and r.source_id like 'eval2-%'
                           ) returning id""",
                        TENANT_ID,
                    )
                    raw = await conn.fetch(
                        "delete from public.raw_events where tenant_id=$1 and source_id like 'eval2-%' returning id",
                        TENANT_ID,
                    )
                print(f"Deleted: {len(emb)} embeddings, {len(dec)} decisions, {len(raw)} raw_events")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
