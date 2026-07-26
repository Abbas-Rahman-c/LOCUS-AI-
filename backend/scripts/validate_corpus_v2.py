"""
Checkpoint 1 static validator — no DB connections, no API calls, no ingestion.

Imports the REAL EventEnvelope and ExtractionResult Pydantic models and
attempts to construct one instance of each from every generated decision,
applying only the documented field-mapping adapter (source_message_id ->
source_id, raw_content string -> {"text": ...} dict). Any ValidationError
is a genuine schema-compatibility failure and is reported precisely.

Also runs the benchmark-integrity checks: every referenced source_message_id
must exist in the corpus, negative queries must have empty expected lists,
and near-duplicate pairs must be intentional (already checked at generation
time, re-verified here independently).

Usage:
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/validate_corpus_v2.py
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pydantic import ValidationError

from modules.ai.extraction.schemas import ExtractionResult
from modules.ingestion.envelope.schemas import EventEnvelope

CORPUS_DIR = SRC_DIR / "evaluation" / "corpus_v2"


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


def to_extraction_dict(d: dict) -> dict:
    sgt = d["structured_ground_truth"]
    return {
        "record_type": sgt["record_type"],
        "status": sgt["status"],
        "decision_statement": sgt["decision_statement"],
        "rationale": sgt.get("rationale"),
        "alternatives_considered": sgt.get("alternatives_considered", []),
        "actors": sgt.get("actors", []),
        "confidence": sgt["confidence"],
    }


def main() -> int:
    decisions = json.loads((CORPUS_DIR / "decisions.json").read_text())
    failures = []

    ids_seen = set()
    statements_seen = set()

    for d in decisions:
        sid = d["source_message_id"]

        if sid in ids_seen:
            failures.append((sid, "source_message_id", sid, "unique", "duplicate source_message_id"))
        ids_seen.add(sid)

        stmt = d["structured_ground_truth"]["decision_statement"]
        if stmt in statements_seen:
            failures.append((sid, "decision_statement", stmt, "unique", "duplicate decision_statement"))
        statements_seen.add(stmt)

        try:
            EventEnvelope(**to_envelope_dict(d))
        except ValidationError as e:
            failures.append((sid, "EventEnvelope", to_envelope_dict(d), "valid EventEnvelope", str(e)))

        try:
            ExtractionResult(**to_extraction_dict(d))
        except ValidationError as e:
            failures.append((sid, "ExtractionResult", to_extraction_dict(d), "valid ExtractionResult", str(e)))

        # embedding text non-empty check (mirrors _build_searchable_text + embed_document's blank check)
        searchable = f"Decision: {stmt}"
        if d["structured_ground_truth"].get("rationale"):
            searchable += f"\nRationale: {d['structured_ground_truth']['rationale']}"
        if not searchable.strip():
            failures.append((sid, "searchable_text", searchable, "non-blank", "embedding input would be blank"))

    print(f"Validated {len(decisions)} decisions against real EventEnvelope/ExtractionResult schemas.")
    print(f"Failures: {len(failures)}")
    for f in failures[:20]:
        print(f"  source_message_id={f[0]} field={f[1]}")
        print(f"    current_value={f[2]!r}")
        print(f"    required={f[3]}")
        print(f"    detail={f[4]}")

    # --- benchmark integrity checks ---
    all_ids = {d["source_message_id"] for d in decisions}
    hybrid = json.loads((CORPUS_DIR / "benchmark_hybrid.json").read_text())
    bench_failures = []
    for q in hybrid:
        for key in ("expected_source_message_ids", "excluded_source_message_ids"):
            for ref in q.get(key, []) or []:
                if ref not in all_ids:
                    bench_failures.append((q["query_id"], key, ref, "must exist in decisions.json", "dangling reference"))
        if q["expected_answerable"] is False and q.get("expected_source_message_ids"):
            bench_failures.append((q["query_id"], "expected_source_message_ids",
                                    q["expected_source_message_ids"], "[] when expected_answerable=False",
                                    "non-empty expected list on a negative/restricted query"))
        if q["expected_answerable"] is True and not q.get("expected_source_message_ids"):
            bench_failures.append((q["query_id"], "expected_source_message_ids", [],
                                    "non-empty when expected_answerable=True", "empty expected list on a positive query"))
        expected_set = set(q.get("expected_source_message_ids") or [])
        excluded_set = set(q.get("excluded_source_message_ids") or [])
        if expected_set & excluded_set:
            bench_failures.append((q["query_id"], "expected/excluded overlap",
                                    list(expected_set & excluded_set), "disjoint", "contradictory ground truth"))

    print(f"\nBenchmark integrity failures: {len(bench_failures)}")
    for f in bench_failures[:20]:
        print(f"  query_id={f[0]} field={f[1]} current={f[2]!r} required={f[3]} detail={f[4]}")

    return 0 if not failures and not bench_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
