"""
Checkpoint 2 — five-record dry run of the approved Option B loading path.

Reused production functions (no bypass, no raw SQL inserts):
  - modules.ingestion.dedup.ledger.mark_seen()
  - modules.decisions.pipeline_persistence.persist_decision_from_extraction()
  - modules.ai.embeddings.service.process_embedding_job()

ExtractionResult is constructed directly in this script (not via Claude
triage/extraction) since the ground truth is already authored — this is
exactly the approved Option B design. 0 Claude calls. Exactly 5 Voyage
document embedding calls (one per record, via process_embedding_job()).
No /search calls, no HTTP requests at all.

Hard ceiling enforced in code: MAX_RECORDS = 5.

Usage:
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/checkpoint2_dry_run.py
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
from modules.ai.embeddings.service import process_embedding_job
from modules.ai.extraction.schemas import ExtractionResult
from modules.decisions.pipeline_persistence import persist_decision_from_extraction
from modules.ingestion.dedup.ledger import mark_seen
from modules.ingestion.envelope.schemas import EventEnvelope
from queues.pgmq.schemas import EmbeddingJob

CORPUS_DIR = SRC_DIR / "evaluation" / "corpus_v2"
TENANT_ID = uuid.UUID("13bcd0fa-1ed9-4634-93c7-278ba97ec658")
MAX_RECORDS = 5


def select_five(decisions: list[dict]) -> list[dict]:
    picks = {}
    for d in decisions:
        rt = d["structured_ground_truth"]["record_type"]
        if "unrestricted_decision" not in picks and rt == "decision" and not d["permission_scope"] and not d["hard_case_tags"]:
            picks["unrestricted_decision"] = d
        elif "action_item" not in picks and rt == "action_item":
            picks["action_item"] = d
        elif "blocker" not in picks and rt == "blocker":
            picks["blocker"] = d
        elif "restricted_decision" not in picks and d["permission_scope"]:
            picks["restricted_decision"] = d
        elif "near_duplicate" not in picks and any(t.startswith("near_duplicate_pair:") for t in d["hard_case_tags"]):
            picks["near_duplicate"] = d
        if len(picks) == 5:
            break
    assert len(picks) == 5, f"could only find {len(picks)}/5 representative categories: {list(picks)}"
    return list(picks.items())


def to_envelope_dict(d: dict) -> dict:
    return {
        "tenant_id": d["tenant_id"],
        "source": d["source"],
        "source_id": d["source_message_id"],
        "actor": d["actor"],
        "thread_ref": d.get("thread_ref"),
        "permission_scope": d.get("permission_scope", []),
        "raw_content": {"text": d["raw_content"]},
        "received_at": d["received_at"],
    }


def to_extraction_result(d: dict) -> ExtractionResult:
    sgt = d["structured_ground_truth"]
    return ExtractionResult(
        record_type=sgt["record_type"],
        status=sgt["status"],
        decision_statement=sgt["decision_statement"],
        rationale=sgt.get("rationale"),
        alternatives_considered=sgt.get("alternatives_considered", []),
        actors=sgt.get("actors", []),
        confidence=sgt["confidence"],
    )


async def main() -> None:
    decisions = json.loads((CORPUS_DIR / "decisions.json").read_text())
    picks = select_five(decisions)

    print("Selected 5 representative records:")
    for category, d in picks:
        print(f"  {category}: {d['source_message_id']} (permission_scope={d['permission_scope']}, "
              f"tags={d['hard_case_tags']})")

    config = get_app_database_config()
    pool = await asyncpg.create_pool(dsn=config.dsn, min_size=1, max_size=5, statement_cache_size=0)
    await init_db_pool(pool)

    voyage_calls = 0
    manifest = []

    async with tenant_connection(TENANT_ID) as conn:
        baseline = dict(await conn.fetchrow(
            """select
                 (select count(*) from public.raw_events where tenant_id=$1) as raw_events,
                 (select count(*) from public.decisions where tenant_id=$1) as decisions,
                 (select count(*) from public.decision_embeddings where tenant_id=$1) as embeddings""",
            TENANT_ID,
        ))
    print(f"\nBaseline counts before dry run (whole tenant): {baseline}")

    try:
        for category, d in picks:
            envelope_payload = EventEnvelope(**to_envelope_dict(d)).model_dump(mode="json")
            raw_event_id = await mark_seen(envelope_payload)
            if raw_event_id is None:
                raise RuntimeError(f"unexpected duplicate for {d['source_message_id']} — dry run must start clean")

            envelope = EventEnvelope(**to_envelope_dict(d))
            extraction = to_extraction_result(d)

            decision_id = await persist_decision_from_extraction(
                pool=pool,
                tenant_id=TENANT_ID,
                event=envelope,
                extraction=extraction,
                origin_raw_event_id=raw_event_id,
                source_permalink=d["source_permalink"],
            )

            await process_embedding_job(pool, EmbeddingJob(tenant_id=TENANT_ID, decision_id=decision_id))
            voyage_calls += 1

            manifest.append({
                "category": category,
                "source_message_id": d["source_message_id"],
                "raw_event_id": str(raw_event_id),
                "decision_id": str(decision_id),
                "permission_scope": d["permission_scope"],
            })
            print(f"  loaded {category}: {d['source_message_id']} -> raw_event_id={raw_event_id} decision_id={decision_id}")

        assert voyage_calls == MAX_RECORDS, f"expected exactly {MAX_RECORDS} Voyage calls, made {voyage_calls}"

        # --- verification ---
        print("\n--- verification ---")
        source_ids = [d["source_message_id"] for _, d in picks]
        async with tenant_connection(TENANT_ID) as conn:
            raw_rows = await conn.fetch(
                "select id, source_id from public.raw_events where tenant_id=$1 and source_id = any($2::text[])",
                TENANT_ID, source_ids,
            )
            decision_rows = await conn.fetch(
                """select d.id, d.origin_raw_event_id, d.permission_scope, r.source_id
                   from public.decisions d join public.raw_events r on r.id = d.origin_raw_event_id
                   where d.tenant_id=$1 and r.source_id = any($2::text[])""",
                TENANT_ID, source_ids,
            )
            embedding_rows = await conn.fetch(
                """select e.decision_id, e.tenant_id, vector_dims(e.embedding) as dim_check
                   from public.decision_embeddings e
                   join public.decisions d on d.id = e.decision_id
                   join public.raw_events r on r.id = d.origin_raw_event_id
                   where d.tenant_id=$1 and r.source_id = any($2::text[])""",
                TENANT_ID, source_ids,
            )

        print(f"raw_events created: {len(raw_rows)} (expected 5)")
        print(f"decisions created: {len(decision_rows)} (expected 5)")
        print(f"embeddings created: {len(embedding_rows)} (expected 5)")
        for r in embedding_rows:
            print(f"  decision_id={r['decision_id']} dim={r['dim_check']} (expected 1024)")
        for r in decision_rows:
            print(f"  decision_id={r['id']} source_id={r['source_id']} permission_scope={r['permission_scope']}")

        async with tenant_connection(TENANT_ID) as conn:
            after = dict(await conn.fetchrow(
                """select
                     (select count(*) from public.raw_events where tenant_id=$1) as raw_events,
                     (select count(*) from public.decisions where tenant_id=$1) as decisions,
                     (select count(*) from public.decision_embeddings where tenant_id=$1) as embeddings""",
                TENANT_ID,
            ))
        print(f"\nWhole-tenant counts after dry run: {after}")
        print(f"Delta: raw_events +{after['raw_events']-baseline['raw_events']}, "
              f"decisions +{after['decisions']-baseline['decisions']}, "
              f"embeddings +{after['embeddings']-baseline['embeddings']} (expected +5/+5/+5)")

        (CORPUS_DIR / "checkpoint2_manifest.json").write_text(json.dumps({
            "baseline": baseline, "after_load": after, "records": manifest,
        }, indent=2))
        print(f"\nManifest written to {CORPUS_DIR / 'checkpoint2_manifest.json'}")
        print(f"Total Voyage calls: {voyage_calls}. Total Claude calls: 0. Total /search calls: 0.")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
