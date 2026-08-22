"""Smoke test: DB connection + pgmq enqueue/read/delete on ingestion queue."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

QUEUE = "ingestion"
TEST_PAYLOAD = {
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "source": "slack",
    "source_id": "local-smoke-test",
    "event_type": "message.created",
    "occurred_at": "2026-07-09T00:00:00Z",
}


def normalize_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> int:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL is not set in backend/.env")
        return 1

    dsn = normalize_dsn(dsn)
    print("Connecting to database...")

    try:
        conn = await asyncpg.connect(dsn, statement_cache_size=0)
    except Exception as exc:
        print(f"ERROR: Could not connect: {exc}")
        print("\nTip: pgmq usually needs a DIRECT Postgres URL, e.g.")
        print("postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres")
        return 1

    try:
        version = await conn.fetchval("select version()")
        print("Connected.")
        print(f"Postgres: {version.split(',')[0]}")

        msg_id = await conn.fetchval(
            "select pgmq.send($1, $2::jsonb)",
            QUEUE,
            json.dumps(TEST_PAYLOAD),
        )
        print(f"Enqueued test message to {QUEUE!r}, msg_id={msg_id}")

        rows = await conn.fetch("select * from pgmq.read($1, $2, $3)", QUEUE, 30, 1)
        if not rows:
            print("ERROR: Message was not readable from queue")
            return 1

        row = dict(rows[0])
        print(f"Read message: msg_id={row.get('msg_id')}, payload={row.get('message')}")

        await conn.execute("select pgmq.delete($1, $2::bigint)", QUEUE, row["msg_id"])
        print("Deleted test message.")

        print("\nSUCCESS: DB + pgmq queue are working.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
