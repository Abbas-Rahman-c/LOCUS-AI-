"""
Runs the combined 60-query benchmark (25 regression + 35 hybrid-focused)
against the real POST /search endpoint, for ONE retrieval mode per
invocation (the server must already be running in that mode — this script
makes no config changes and does not start/stop the server).

Scoring logic (identical across all 3 modes, corrected citation scoring
carried over from the Stage 2/3 evaluations):
  - For expected_answerable=True, non-multi: pass if any expected id is
    cited AND no excluded id leaked.
  - For expected_answerable=True, multi-decision: pass if ALL expected ids
    are cited AND no excluded id leaked (strict). Decision-level accuracy
    is tracked separately as the fraction of expected ids cited.
  - For expected_answerable=False WITH an excluded-id list (permission-
    restricted): pass if none of the excluded ids leaked into citations or
    answer text. Citation COUNT is not checked — Claude's refusal
    explanation can incidentally reference a decision by number without
    actually leaking its content, which is exactly the false-positive this
    correction fixes (root-caused in the earlier Stage 2 comparative run).
  - For expected_answerable=False with NO excluded-id list (genuine
    no-answer): pass only if zero citations were produced — there is
    nothing legitimate to cite, so any citation is a false positive.

Rate-limit-avoiding schedule: 60 queries per mode are split into 3
sequential batches of 20, with a 5-minute wait between batches (not a
reactive retry-after-429 pattern) — stays under the 20 requests/tenant/
5-minute limiter with margin.

Usage:
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/run_full_benchmark.py <mode>
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import httpx
from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

from modules.auth.service import issue_tenant_jwt

BASE_URL = "http://localhost:8000"
TENANT_ID = "13bcd0fa-1ed9-4634-93c7-278ba97ec658"
CORPUS_DIR = SRC_DIR / "evaluation" / "corpus_v2"
RESULTS_DIR = SRC_DIR / "evaluation" / "results_v2"
BATCH_SIZE = 20
BATCH_WAIT_SECONDS = 300

# Segment mapping per the user's exact 9 requested segments.
SEGMENT_OVERRIDE = {
    "hyb-acr-01": "no_answer",
    "hyb-acr-02": "semantic_favored",
    "hyb-acr-03": "semantic_favored",
    "hyb-multi-01": "hybrid_favored", "hyb-multi-02": "hybrid_favored",
    "hyb-multi-03": "hybrid_favored", "hyb-multi-04": "hybrid_favored",
}
HYBRID_CATEGORY_TO_SEGMENT = {
    "keyword_favored": "keyword_favored", "semantic_favored": "semantic_favored",
    "hybrid_favored": "hybrid_favored", "identifier_lookup": "identifier_lookup",
    "entity_lookup": "entity_lookup", "near_duplicate_disambiguation": "near_duplicate",
    "permission": "permission", "no_answer": "no_answer",
    "acronym_expanded_form": "semantic_favored", "multi_decision": "hybrid_favored",
}


def load_queries() -> list[dict]:
    regression = json.loads((CORPUS_DIR / "benchmark_regression.json").read_text())
    hybrid = json.loads((CORPUS_DIR / "benchmark_hybrid.json").read_text())
    manifest = json.loads((CORPUS_DIR / "load_manifest.json").read_text())
    sid_to_did = {m["source_message_id"]: m["decision_id"] for m in manifest}

    queries = []
    for q in regression:
        queries.append({
            "query_id": q["test_id"], "suite": "regression", "segment": "regression",
            "question": q["question"], "expected_decision_ids": q["expected_decision_ids"],
            "excluded_decision_ids": q.get("excluded_decision_ids", []),
            "expected_answerable": q["expected_answerable"],
            "is_multi": q["category"] == "multi_decision",
        })
    for q in hybrid:
        expected = [sid_to_did[sid] for sid in q.get("expected_source_message_ids", [])]
        excluded = [sid_to_did[sid] for sid in q.get("excluded_source_message_ids", [])]
        segment = SEGMENT_OVERRIDE.get(q["query_id"]) or HYBRID_CATEGORY_TO_SEGMENT[q["category"]]
        queries.append({
            "query_id": q["query_id"], "suite": "hybrid", "segment": segment,
            "question": q["question"], "expected_decision_ids": expected,
            "excluded_decision_ids": excluded, "expected_answerable": q["expected_answerable"],
            "is_multi": q["category"] == "multi_decision",
        })

    assert len(queries) == 60, f"expected 60 combined queries, got {len(queries)}"
    return queries


def evaluate(q: dict, response_json: dict, wall_ms: float) -> dict:
    citations = response_json.get("citations", [])
    cited_ids = [c["decision_id"] for c in citations]
    answer = response_json.get("answer", "") or ""
    expected = q["expected_decision_ids"]
    excluded = q["excluded_decision_ids"]

    excluded_leak = any(x in cited_ids or x in answer for x in excluded)

    decision_level_recall = None
    if q["expected_answerable"]:
        if q["is_multi"]:
            hit_count = sum(1 for e in expected if e in cited_ids)
            decision_level_recall = hit_count / len(expected) if expected else None
            passed = hit_count == len(expected) and not excluded_leak
        else:
            passed = any(e in cited_ids for e in expected) and not excluded_leak
    else:
        if excluded:
            passed = not excluded_leak
        else:
            passed = len(citations) == 0 and not excluded_leak

    rank = None
    for c in sorted(citations, key=lambda c: c["decision_number"]):
        if c["decision_id"] in expected:
            rank = c["decision_number"]
            break

    return {
        "query_id": q["query_id"], "suite": q["suite"], "segment": q["segment"],
        "question": q["question"], "expected_decision_ids": expected, "excluded_decision_ids": excluded,
        "retrieved_decision_ids": cited_ids,
        "retrieved_ranking": [{"decision_number": c["decision_number"], "decision_id": c["decision_id"],
                                "confidence": c["confidence"]} for c in citations],
        "first_expected_rank": rank, "decision_level_recall": decision_level_recall,
        "generated_answer": answer, "citations": citations,
        "wall_clock_ms": round(wall_ms, 1), "expected_answerable": q["expected_answerable"],
        "is_multi": q["is_multi"], "status": "PASS" if passed else "FAIL",
    }


def main():
    mode = sys.argv[1]
    assert mode in ("semantic_only", "keyword_only", "hybrid_rrf")

    queries = load_queries()
    token = issue_tenant_jwt(user_id=f"finaleval-{mode}", tenant_id=TENANT_ID, role="member")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    results = []
    print(f"Running {len(queries)} queries against {BASE_URL}/search in mode={mode}, "
          f"batches of {BATCH_SIZE} with {BATCH_WAIT_SECONDS}s waits between batches")

    with httpx.Client(timeout=30.0) as client:
        for batch_start in range(0, len(queries), BATCH_SIZE):
            batch = queries[batch_start:batch_start + BATCH_SIZE]
            print(f"\n--- batch {batch_start // BATCH_SIZE + 1}: queries {batch_start+1}-{batch_start+len(batch)} ---")
            for i, q in enumerate(batch, start=batch_start + 1):
                start = time.perf_counter()
                try:
                    resp = client.post(f"{BASE_URL}/search", headers=headers, json={"question": q["question"]})
                    wall_ms = (time.perf_counter() - start) * 1000
                    resp.raise_for_status()
                    record = evaluate(q, resp.json(), wall_ms)
                except Exception as exc:
                    wall_ms = (time.perf_counter() - start) * 1000
                    record = {"query_id": q["query_id"], "suite": q["suite"], "segment": q["segment"],
                              "question": q["question"], "status": "ERROR",
                              "error": f"{type(exc).__name__}: {exc}", "wall_clock_ms": round(wall_ms, 1),
                              "expected_answerable": q["expected_answerable"], "is_multi": q["is_multi"],
                              "expected_decision_ids": q["expected_decision_ids"],
                              "excluded_decision_ids": q["excluded_decision_ids"],
                              "retrieved_decision_ids": [], "retrieved_ranking": [],
                              "first_expected_rank": None, "decision_level_recall": None,
                              "generated_answer": None, "citations": []}
                print(f"  [{i}/{len(queries)}] {q['query_id']}: {record['status']}  latency={record['wall_clock_ms']}ms")
                results.append(record)

            if batch_start + BATCH_SIZE < len(queries):
                print(f"  waiting {BATCH_WAIT_SECONDS}s before next batch (proactive rate-limit avoidance)...")
                time.sleep(BATCH_WAIT_SECONDS)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_file = RESULTS_DIR / f"final_{mode}_{ts}.json"
    out_file.write_text(json.dumps(results, indent=2))
    print(f"\nResults written to {out_file}")
    print(f"RESULTS_FILE={out_file}")


if __name__ == "__main__":
    main()
