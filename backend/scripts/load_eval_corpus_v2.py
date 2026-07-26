"""
CHECKPOINT 3 ARTIFACT — full 250-record loader. WRITTEN BUT NOT EXECUTED.

Do not run this file until explicitly approved. This docstring itself is
part of the approval package: it states exactly what running it would do.

Loads all 250 corpus_v2 decisions via the approved Option B path — the
same three reused production functions as the Checkpoint 2 dry run:
  - modules.ingestion.dedup.ledger.mark_seen()
  - modules.decisions.pipeline_persistence.persist_decision_from_extraction()
  - modules.ai.embeddings.service.process_embedding_job()
No raw SQL inserts. No Claude calls (ExtractionResult is constructed
directly from pre-authored ground truth, exactly as validated in
Checkpoint 1). No /search calls. No retrieval config is read or changed.

HARD CEILINGS (enforced in code, not just documented):
  - MAX_RECORDS = 250 — the script asserts len(decisions) == 250 and
    refuses to process a 251st record even if the input file were tampered
    with.
  - 0 Claude triage calls, 0 Claude extraction calls (no Claude client is
    even imported).
  - <= 250 Voyage document embedding calls (exactly one per successfully
    persisted decision; a resumed run makes fewer).
  - 0 /search calls (no httpx client, no HTTP requests at all).
  - HARD STOP on the first unhandled exception: the manifest entry for the
    failing record is written first, then the exception is re-raised and
    the process exits non-zero. No catch-and-continue on persistence or
    embedding errors (mirrors create_eval_corpus.py's Stage 1 fix).
  - Resume logic keys ONLY on source_id values starting with "eval2-": if
    mark_seen() reports a duplicate for such an id, the script looks up
    the existing raw_event_id and checks whether a decision already
    exists for it; if so it skips re-persisting/re-embedding and records
    it as "already loaded"; if a raw_event exists but no decision yet
    (partial prior failure), it resumes from persistence using the same
    pre-authored ExtractionResult. No other source_id prefix is ever
    touched by this resume logic.
  - No UPDATE statements anywhere in this script — every DB call is
    either a read (SELECT) or an INSERT guarded by the same
    ON CONFLICT DO NOTHING / idempotency check the production functions
    already use. No existing (non "eval2-*") row is ever modified.

Usage (NOT to be run without separate approval):
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/load_eval_corpus_v2.py

Reads:  src/evaluation/corpus_v2/decisions.json
Writes: src/evaluation/corpus_v2/load_manifest.json (after every record)
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
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
from modules.ai.embeddings.service import process_embedding_job
from modules.ai.extraction.schemas import ExtractionResult
from modules.decisions.pipeline_persistence import persist_decision_from_extraction
from modules.ingestion.dedup.ledger import mark_seen
from modules.ingestion.envelope.schemas import EventEnvelope
from queues.pgmq.schemas import EmbeddingJob

CORPUS_DIR = SRC_DIR / "evaluation" / "corpus_v2"
TENANT_ID = uuid.UUID("13bcd0fa-1ed9-4634-93c7-278ba97ec658")
MAX_RECORDS = 250
MANIFEST_PATH = CORPUS_DIR / "load_manifest.json"


class CallLimitExceeded(Exception):
    pass


def to_envelope_dict(d: dict) -> dict:
    return {
        "tenant_id": d["tenant_id"], "source": d["source"], "source_id": d["source_message_id"],
        "actor": d["actor"], "thread_ref": d.get("thread_ref"),
        "permission_scope": d.get("permission_scope", []),
        "raw_content": {"text": d["raw_content"]}, "received_at": d["received_at"],
    }


def to_extraction_result(d: dict) -> ExtractionResult:
    sgt = d["structured_ground_truth"]
    return ExtractionResult(
        record_type=sgt["record_type"], status=sgt["status"],
        decision_statement=sgt["decision_statement"], rationale=sgt.get("rationale"),
        alternatives_considered=sgt.get("alternatives_considered", []),
        actors=sgt.get("actors", []), confidence=sgt["confidence"],
    )


async def _find_existing(conn, source_id: str) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Read-only: for an eval2-* source_id, find existing raw_event_id / decision_id, if any."""
    raw_row = await conn.fetchrow(
        "select id from public.raw_events where tenant_id=$1 and source_id=$2",
        TENANT_ID, source_id,
    )
    if raw_row is None:
        return None, None
    dec_row = await conn.fetchrow(
        "select id from public.decisions where tenant_id=$1 and origin_raw_event_id=$2",
        TENANT_ID, raw_row["id"],
    )
    return raw_row["id"], (dec_row["id"] if dec_row else None)


def _write_manifest(manifest: list[dict]) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))


async def main() -> None:
    decisions = json.loads((CORPUS_DIR / "decisions.json").read_text())
    assert len(decisions) == MAX_RECORDS, f"expected exactly {MAX_RECORDS}, got {len(decisions)}"
    assert all(d["source_message_id"].startswith("eval2-") for d in decisions)

    config = get_app_database_config()
    pool = await asyncpg.create_pool(dsn=config.dsn, min_size=1, max_size=5, statement_cache_size=0)
    await init_db_pool(pool)

    manifest: list[dict] = []
    voyage_calls = 0
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        async with tenant_connection(TENANT_ID) as conn:
            baseline = dict(await conn.fetchrow(
                """select (select count(*) from public.raw_events where tenant_id=$1) as raw_events,
                          (select count(*) from public.decisions where tenant_id=$1) as decisions,
                          (select count(*) from public.decision_embeddings where tenant_id=$1) as embeddings""",
                TENANT_ID,
            ))

        for i, d in enumerate(decisions, start=1):
            sid = d["source_message_id"]
            try:
                async with tenant_connection(TENANT_ID) as conn:
                    existing_raw_id, existing_decision_id = await _find_existing(conn, sid)

                if existing_decision_id is not None:
                    manifest.append({"source_message_id": sid, "raw_event_id": str(existing_raw_id),
                                      "decision_id": str(existing_decision_id), "status": "already_loaded"})
                    print(f"[{i}/{MAX_RECORDS}] {sid}: already loaded, skipping")
                    _write_manifest(manifest)
                    continue

                envelope = EventEnvelope(**to_envelope_dict(d))
                extraction = to_extraction_result(d)

                if existing_raw_id is not None:
                    raw_event_id = existing_raw_id
                else:
                    payload = envelope.model_dump(mode="json")
                    raw_event_id = await mark_seen(payload)
                    if raw_event_id is None:
                        raise RuntimeError(f"unexpected mark_seen conflict for fresh id {sid}")

                decision_id = await persist_decision_from_extraction(
                    pool=pool, tenant_id=TENANT_ID, event=envelope, extraction=extraction,
                    origin_raw_event_id=raw_event_id, source_permalink=d["source_permalink"],
                )

                await process_embedding_job(pool, EmbeddingJob(tenant_id=TENANT_ID, decision_id=decision_id))
                voyage_calls += 1
                if voyage_calls > MAX_RECORDS:
                    raise CallLimitExceeded(f"Voyage call ceiling ({MAX_RECORDS}) exceeded")

                manifest.append({"source_message_id": sid, "raw_event_id": str(raw_event_id),
                                  "decision_id": str(decision_id), "status": "loaded"})
                print(f"[{i}/{MAX_RECORDS}] {sid}: loaded -> decision_id={decision_id}")
                _write_manifest(manifest)

                completed = sum(1 for m in manifest if m["status"] in ("loaded", "already_loaded"))
                if completed % 25 == 0:
                    print(f"--- progress: {completed}/{MAX_RECORDS} completed, {voyage_calls} Voyage calls so far ---")

            except Exception as exc:
                manifest.append({"source_message_id": sid, "status": "FAILED",
                                  "error": f"{type(exc).__name__}: {exc}"})
                _write_manifest(manifest)
                last_success = next((m for m in reversed(manifest) if m["status"] in ("loaded", "already_loaded")), None)
                remaining = decisions[i:]
                print(f"\n=== HARD STOP: unhandled exception ===")
                print(f"source_message_id: {sid}")
                print(f"exception: {type(exc).__name__}: {exc}")
                print(f"last successful manifest entry: {json.dumps(last_success)}")
                print(f"remaining records: {len(remaining)} (from index {i} of {MAX_RECORDS})")
                print(f"=== no automatic retry — stopping ===\n")
                raise  # hard stop, no catch-and-continue

        async with tenant_connection(TENANT_ID) as conn:
            after = dict(await conn.fetchrow(
                """select (select count(*) from public.raw_events where tenant_id=$1) as raw_events,
                          (select count(*) from public.decisions where tenant_id=$1) as decisions,
                          (select count(*) from public.decision_embeddings where tenant_id=$1) as embeddings""",
                TENANT_ID,
            ))
            dup_check = await conn.fetch(
                """select origin_raw_event_id, count(*) from public.decisions
                   where tenant_id=$1 and origin_raw_event_id in (
                     select id from public.raw_events where tenant_id=$1 and source_id like 'eval2-%'
                   ) group by origin_raw_event_id having count(*) > 1""",
                TENANT_ID,
            )

        print(f"\nBaseline: {baseline}")
        print(f"After load: {after}")
        print(f"Voyage calls made: {voyage_calls}. Claude calls made: 0. /search calls made: 0.")
        print(f"Duplicate decisions per raw_event: {len(dup_check)} (expected 0)")
        print(f"Manifest: {MANIFEST_PATH}")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
