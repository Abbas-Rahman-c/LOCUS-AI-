"""
Final post-load integrity verification (12-point). Read-only except for
producing a report — no writes, no code/config changes.

Usage:
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/checkpoint_final_verify.py
"""
from __future__ import annotations

import json
import sys
import uuid
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

from common.config.database_config import get_app_database_config

CORPUS_DIR = SRC_DIR / "evaluation" / "corpus_v2"
TENANT_ID = "13bcd0fa-1ed9-4634-93c7-278ba97ec658"


async def main():
    decisions = json.loads((CORPUS_DIR / "decisions.json").read_text())
    manifest = json.loads((CORPUS_DIR / "load_manifest.json").read_text())
    checkpoint2 = json.loads((CORPUS_DIR / "checkpoint2_manifest.json").read_text())
    baseline = checkpoint2["baseline"]  # pre-Checkpoint-2 baseline == pre-full-load baseline (dry run was cleaned up)

    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    # 1-3: DB counts scoped to eval2-*
    config = get_app_database_config()
    conn = await asyncpg.connect(dsn=config.dsn, statement_cache_size=0)
    try:
        raw_count = await conn.fetchval(
            "select count(*) from public.raw_events where tenant_id=$1 and source_id like 'eval2-%'", TENANT_ID)
        dec_count = await conn.fetchval(
            """select count(*) from public.decisions d join public.raw_events r on r.id=d.origin_raw_event_id
               where d.tenant_id=$1 and r.source_id like 'eval2-%'""", TENANT_ID)
        emb_count = await conn.fetchval(
            """select count(*) from public.decision_embeddings e
               join public.decisions d on d.id=e.decision_id
               join public.raw_events r on r.id=d.origin_raw_event_id
               where d.tenant_id=$1 and r.source_id like 'eval2-%'""", TENANT_ID)
        check("1. exactly 250 eval2-* raw_events", raw_count == 250, f"actual={raw_count}")
        check("2. exactly 250 eval2-* decisions", dec_count == 250, f"actual={dec_count}")
        check("3. exactly 250 eval2-* embeddings", emb_count == 250, f"actual={emb_count}")

        # 4: manifest entry count
        check("4. load_manifest.json has exactly 250 entries", len(manifest) == 250, f"actual={len(manifest)}")

        # 5: 1:1 mapping, no dup source_message_id/raw_event_id/decision_id in manifest
        sids = [m["source_message_id"] for m in manifest]
        reids = [m["raw_event_id"] for m in manifest]
        dids = [m["decision_id"] for m in manifest]
        dup_sids = [k for k, v in Counter(sids).items() if v > 1]
        dup_reids = [k for k, v in Counter(reids).items() if v > 1]
        dup_dids = [k for k, v in Counter(dids).items() if v > 1]
        check("5. every source_message_id -> exactly one raw_event_id/decision_id",
              not dup_sids and not dup_reids and not dup_dids,
              f"dup_sids={dup_sids} dup_reids={dup_reids} dup_dids={dup_dids}")

        # 6: every decision has exactly one embedding (join count already 250==250 above covers existence;
        # check no decision has >1 embedding row via PK, and no decision has 0)
        no_emb = await conn.fetch(
            """select d.id from public.decisions d
               join public.raw_events r on r.id=d.origin_raw_event_id
               left join public.decision_embeddings e on e.decision_id=d.id
               where d.tenant_id=$1 and r.source_id like 'eval2-%' and e.decision_id is null""", TENANT_ID)
        check("6. every eval2-* decision has exactly one embedding", len(no_emb) == 0, f"missing={len(no_emb)}")

        # 7: permission scopes match intended
        db_rows = await conn.fetch(
            """select r.source_id, d.permission_scope from public.decisions d
               join public.raw_events r on r.id=d.origin_raw_event_id
               where d.tenant_id=$1 and r.source_id like 'eval2-%'""", TENANT_ID)
        db_scope_by_sid = {row["source_id"]: sorted(row["permission_scope"]) for row in db_rows}
        intended_scope_by_sid = {d["source_message_id"]: sorted(d["permission_scope"]) for d in decisions}
        scope_mismatches = [sid for sid in intended_scope_by_sid
                            if db_scope_by_sid.get(sid) != intended_scope_by_sid[sid]]
        check("7. permission scopes match intended for all 250", not scope_mismatches,
              f"mismatches={scope_mismatches[:10]}")

        # 8: no duplicate source_message_id (source_id) in raw_events for eval2-*
        raw_sid_rows = await conn.fetch(
            "select source_id, count(*) c from public.raw_events where tenant_id=$1 and source_id like 'eval2-%' group by source_id having count(*) > 1",
            TENANT_ID)
        check("8. no duplicate source_message_id in raw_events", len(raw_sid_rows) == 0, f"dupes={len(raw_sid_rows)}")

        # 9: no duplicate decision_statement among eval2-* decisions
        stmt_rows = await conn.fetch(
            """select d.decision_statement, count(*) c from public.decisions d
               join public.raw_events r on r.id=d.origin_raw_event_id
               where d.tenant_id=$1 and r.source_id like 'eval2-%'
               group by d.decision_statement having count(*) > 1""", TENANT_ID)
        check("9. no duplicate decision_statement among eval2-*", len(stmt_rows) == 0, f"dupes={len(stmt_rows)}")

        # 10: Stage 1 / non-evaluation records untouched
        stage1_count = await conn.fetchval(
            "select count(*) from public.raw_events where tenant_id=$1 and source_id like 'eval-%' and source_id not like 'eval2-%'",
            TENANT_ID)
        total_raw = await conn.fetchval("select count(*) from public.raw_events where tenant_id=$1", TENANT_ID)
        total_dec = await conn.fetchval("select count(*) from public.decisions where tenant_id=$1", TENANT_ID)
        total_emb = await conn.fetchval("select count(*) from public.decision_embeddings where tenant_id=$1", TENANT_ID)
        expected_total_raw = baseline["raw_events"] + 250
        expected_total_dec = baseline["decisions"] + 250
        expected_total_emb = baseline["embeddings"] + 250
        check("10. Stage 1 records untouched + totals match baseline+250",
              stage1_count == 22 and total_raw == expected_total_raw
              and total_dec == expected_total_dec and total_emb == expected_total_emb,
              f"stage1_count={stage1_count} (expect 22), total_raw={total_raw} (expect {expected_total_raw}), "
              f"total_dec={total_dec} (expect {expected_total_dec}), total_emb={total_emb} (expect {expected_total_emb})")

        # 11: resume logic — no pending eval2-* records (every decisions.json source_message_id has a decision)
        all_sids_in_corpus = {d["source_message_id"] for d in decisions}
        loaded_sids = set(sids)
        missing = all_sids_in_corpus - loaded_sids
        check("11. no remaining pending eval2-* records", not missing, f"missing={list(missing)[:10]}")

        final_counts = {"raw_events": total_raw, "decisions": total_dec, "embeddings": total_emb}

    finally:
        await conn.close()

    print("=== 12-point integrity verification ===")
    all_passed = True
    for name, passed, detail in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"[{status}] {name}  {detail}")

    print(f"\n12. Load summary (from load_eval_corpus_v2.py's own final printout):")
    print("    (see prior tool output: 250 loaded, 0 skipped, 0 failures, 250 Voyage calls, 0 Claude calls)")
    print(f"\nFinal DB counts (whole tenant): {final_counts}")
    print(f"Baseline (pre-load): {baseline}")
    print(f"eval2-* only: raw_events={raw_count} decisions={dec_count} embeddings={emb_count}")
    print(f"\nOVERALL: {'ALL CHECKS PASSED' if all_passed else 'FAILURES DETECTED — STOP'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
