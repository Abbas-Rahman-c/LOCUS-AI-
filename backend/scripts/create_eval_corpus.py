"""
One-shot, bounded ingestion script — creates the RAG-evaluation corpus by
running each authored message in eval_corpus_messages.json through the real
production ingestion pipeline: the exact same functions
queues/workers/event_worker.py and queues/workers/embedding_worker.py call,
just driven by a finite list instead of an infinite pgmq-polling loop.

Reused production functions (no bypass, no reimplementation):
  - modules.ingestion.dedup.ledger.mark_seen()
  - modules.ai.pipeline.service.process_and_persist_event()
  - modules.ai.embeddings.service.process_embedding_job()

After process_and_persist_event() enqueues an embedding job onto the real
pgmq "embedding_queue", this script reads that exact message back off the
queue and deletes it after processing — the same read -> process -> delete
contract embedding_worker.py uses, just for one message per iteration
instead of polling forever.

HARD LIMITS (enforced in code, not just documented):
  - at most MAX_MESSAGES (22) source messages processed
  - at most MAX_MESSAGES Claude Haiku triage calls
  - at most MAX_MESSAGES Claude Haiku extraction calls
  - at most MAX_MESSAGES Voyage embedding calls
  - strictly sequential, no concurrency, no retries, no recursion
  - no queue worker started; the script reads at most one message per
    iteration and exits when the input list is exhausted

Usage (from backend/, with the project venv active):
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/create_eval_corpus.py

Reads:  scripts/eval_corpus_messages.json   (ground truth, authored before ingestion)
Writes: src/evaluation/corpus_manifest.json (what actually happened, written after every message)
"""
from __future__ import annotations

import asyncio
import json
import sys
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
from modules.ai.pipeline.service import IngestionServiceError, process_and_persist_event
from modules.ai.triage.schemas import TriageDecision
from modules.ingestion.dedup.ledger import mark_seen
from modules.ingestion.envelope.schemas import EventEnvelope
from queues.pgmq.client import PgmqClient, init_pgmq_client
from queues.pgmq.queues import QueueName
from queues.pgmq.schemas import EmbeddingJob

MAX_MESSAGES = 22
MESSAGES_FILE = Path(__file__).resolve().parent / "eval_corpus_messages.json"
MANIFEST_FILE = SRC_DIR / "evaluation" / "corpus_manifest.json"


class CallLimitExceeded(RuntimeError):
    """Raised the instant any external-call counter would exceed MAX_MESSAGES."""


def _bump(counter: dict, key: str) -> None:
    counter[key] += 1
    if counter[key] > MAX_MESSAGES:
        raise CallLimitExceeded(
            f"HARD STOP: {key} call count reached {counter[key]}, "
            f"exceeding the limit of {MAX_MESSAGES}. Aborting immediately."
        )


async def _find_existing_raw_event_id(tenant_id, source: str, source_id: str):
    """Read-only lookup of an already-stored raw_events row's id.

    Only ever called from the eval-* resume path below — never for a
    production event, and never performs a write.
    """
    async with tenant_connection(tenant_id) as conn:
        row = await conn.fetchrow(
            "select id from public.raw_events "
            "where tenant_id = $1 and source = $2 and source_id = $3",
            tenant_id,
            source,
            source_id,
        )
    return row["id"] if row else None


async def _find_existing_decision_id(tenant_id, raw_event_id):
    """Read-only lookup: has this raw_event already produced a persisted decision?

    Only ever called from the eval-* resume path below.
    """
    async with tenant_connection(tenant_id) as conn:
        row = await conn.fetchrow(
            "select id from public.decisions "
            "where tenant_id = $1 and origin_raw_event_id = $2",
            tenant_id,
            raw_event_id,
        )
    return row["id"] if row else None


async def _fetch_and_delete_embedding_message(client: PgmqClient, decision_id) -> dict | None:
    """Read the embedding job this run just enqueued, matched by decision_id.

    Mirrors queues/workers/embedding_worker.py's read -> process -> delete
    contract for exactly one message; never polls, never loops.
    """
    messages = await client.read(QueueName.EMBEDDING, vt=60, batch=1)
    if not messages:
        return None
    msg = messages[0]
    raw = msg["message"]
    payload = raw if isinstance(raw, dict) else json.loads(raw)
    if payload.get("decision_id") != str(decision_id):
        # Defensive: should never happen in a fresh, single-writer run —
        # fail loudly rather than silently process the wrong job.
        raise RuntimeError(
            f"Embedding queue message mismatch: expected decision_id={decision_id}, "
            f"got {payload.get('decision_id')}. Refusing to guess."
        )
    return {"msg_id": msg["msg_id"], "payload": payload}


async def main() -> None:
    messages = json.loads(MESSAGES_FILE.read_text())
    if len(messages) > MAX_MESSAGES:
        raise SystemExit(
            f"Refusing to run: {len(messages)} messages in {MESSAGES_FILE.name} "
            f"exceeds the hard limit of {MAX_MESSAGES}."
        )

    config = get_app_database_config()
    if not config.dsn:
        raise SystemExit("APP_DATABASE_URL is not set — check backend/.env")

    pool = await asyncpg.create_pool(
        dsn=config.dsn, min_size=1, max_size=5, statement_cache_size=0
    )
    await init_db_pool(pool)
    await init_pgmq_client(pool)
    pgmq_client = PgmqClient(pool)

    counters = {"triage": 0, "extraction": 0, "voyage": 0}
    manifest: list[dict] = []
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        for i, msg in enumerate(messages, start=1):
            print(
                f"[{i}/{len(messages)}] {msg['source_message_id']} "
                f"({msg['source']}, {msg['category']})"
            )
            print(f"  question: {msg['intended_ground_truth']['decision_statement'][:90]}")
            print(
                f"  cumulative before this case -> "
                f"triage={counters['triage']} extraction={counters['extraction']} voyage={counters['voyage']}"
            )

            entry = {
                "source_message_id": msg["source_message_id"],
                "source": msg["source"],
                "category": msg["category"],
                "intended_ground_truth": msg["intended_ground_truth"],
                "triage_result": None,
                "decision_id": None,
                "extracted_statement": None,
                "permission_scope": msg.get("permission_scope", []),
                "embedding_status": "not_attempted",
                "error": None,
            }

            try:
                envelope = EventEnvelope(
                    tenant_id=msg["tenant_id"],
                    source=msg["source"],
                    source_id=msg["source_message_id"],
                    actor=msg["actor"],
                    thread_ref=msg.get("thread_ref"),
                    permission_scope=msg.get("permission_scope", []),
                    raw_content=msg["raw_content"],
                    received_at=msg["received_at"],
                )

                raw_event_id = await mark_seen(envelope.model_dump(mode="json"))
                if raw_event_id is None:
                    if not msg["source_message_id"].startswith("eval-"):
                        # Not an evaluation message — preserve original dedup
                        # behavior exactly. Never resume production events.
                        entry["error"] = "duplicate — already present in raw_events, skipped"
                        print("  -> SKIPPED (duplicate)")
                        manifest.append(entry)
                        MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))
                        continue

                    # eval-* resume path: the raw event was already stored (a
                    # prior run got this far), but that alone doesn't tell us
                    # whether a decision was ever persisted from it. Check
                    # before doing anything else.
                    existing_raw_event_id = await _find_existing_raw_event_id(
                        envelope.tenant_id, msg["source"], msg["source_message_id"]
                    )
                    if existing_raw_event_id is None:
                        raise RuntimeError(
                            f"mark_seen() reported a duplicate for "
                            f"{msg['source_message_id']} but no matching raw_events "
                            f"row was found — refusing to guess."
                        )

                    existing_decision_id = await _find_existing_decision_id(
                        envelope.tenant_id, existing_raw_event_id
                    )
                    if existing_decision_id is not None:
                        # Already fully processed in an earlier run — never
                        # re-triage, re-extract, or create a second decision.
                        entry["decision_id"] = str(existing_decision_id)
                        entry["embedding_status"] = "already existed from a prior run"
                        print(
                            f"  -> ALREADY DONE (decision {existing_decision_id} "
                            f"already exists) — not reprocessing"
                        )
                        manifest.append(entry)
                        MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))
                        continue

                    # Raw event exists but no decision was ever persisted from
                    # it (exactly what happened to eval-eng-01) — resume using
                    # the existing raw_event_id. No new raw_events row is
                    # inserted; the normal triage/extraction/persist/embed
                    # path below runs exactly as it would for a fresh message.
                    print(
                        f"  -> RESUMING from existing raw_event {existing_raw_event_id} "
                        f"(no decision persisted yet)"
                    )
                    raw_event_id = existing_raw_event_id

                _bump(counters, "triage")  # process_and_persist_event always triages once

                result = await process_and_persist_event(
                    pool,
                    envelope,
                    origin_raw_event_id=raw_event_id,
                    source_permalink=msg.get("source_permalink"),
                )
                entry["triage_result"] = result.triage.decision.value

                if result.triage.decision != TriageDecision.DISCARD:
                    _bump(counters, "extraction")

                if result.persisted:
                    entry["decision_id"] = str(result.decision_id)
                    entry["extracted_statement"] = result.extraction.decision_statement

                    _bump(counters, "voyage")
                    job_msg = await _fetch_and_delete_embedding_message(
                        pgmq_client, result.decision_id
                    )
                    if job_msg is None:
                        # No exception to raise, but this is a real failure —
                        # halt rather than leave a persisted decision with no
                        # embedding and silently move on.
                        raise RuntimeError(
                            f"No embedding_queue message found for decision "
                            f"{result.decision_id} — expected exactly one after "
                            f"process_and_persist_event() enqueued it."
                        )
                    job = EmbeddingJob.model_validate(job_msg["payload"])
                    await process_embedding_job(pool, job)
                    await pgmq_client.delete(QueueName.EMBEDDING, job_msg["msg_id"])
                    entry["embedding_status"] = "embedded"
                else:
                    entry["embedding_status"] = "not_applicable (DISCARD)"

                print(
                    f"  -> triage={entry['triage_result']} decision_id={entry['decision_id']} "
                    f"embedding={entry['embedding_status']} error={entry['error']}"
                )
                manifest.append(entry)
                MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))

            except CallLimitExceeded as exc:
                entry["error"] = f"call limit exceeded: {exc}"
                print(f"  -> HARD STOP (call limit exceeded): {exc}")
                manifest.append(entry)
                MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))
                raise
            except IngestionServiceError as exc:
                entry["error"] = f"pipeline failed: {exc}"
                print(f"  -> HALTING (pipeline error): {exc}")
                manifest.append(entry)
                MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))
                raise
            except Exception as exc:
                entry["error"] = f"unexpected error: {type(exc).__name__}: {exc}"
                print(f"  -> HALTING (unexpected error): {type(exc).__name__}: {exc}")
                manifest.append(entry)
                MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))
                raise
    finally:
        await pool.close()

    print()
    print(
        f"DONE. messages_processed={len(manifest)} "
        f"triage_calls={counters['triage']} extraction_calls={counters['extraction']} "
        f"voyage_calls={counters['voyage']}"
    )
    print(f"Manifest written to {MANIFEST_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
