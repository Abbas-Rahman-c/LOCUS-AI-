"""
One-shot, bounded Stage 2 evaluation runner — executes the 25 approved
queries against the REAL POST /search endpoint (not the internal service
function), sequentially, exactly once each, and computes retrieval/citation/
permission/no-answer metrics from the actual responses.

Reused production function (no bypass): modules.auth.service.issue_tenant_jwt()
to mint the Bearer token used by every request — the same pattern the
repository's own tests use. Nothing else is imported from the application;
every /search call goes through the real HTTP endpoint, real auth
dependency, real permission-scope resolution, real retrieval, real Claude
call.

HARD LIMITS:
  - exactly 25 queries, defined inline below, sequential, no concurrency
  - exactly 1 HTTP request per query (no automatic retries)
  - 1 Voyage + 1 Claude call per query (guaranteed by the endpoint's own
    code path, not something this script can violate)
  - no retrieval logic, prompts, or ranking are touched by this script

Usage:
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/run_stage2_eval.py
"""
from __future__ import annotations

import json
import re
import statistics
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
RESULTS_DIR = SRC_DIR / "evaluation" / "results"
REFUSAL_TEXT = "I couldn't find enough information in the available decisions."

# ---------------------------------------------------------------------------
# The 25 approved queries (verbatim from the approved Stage 2 test plan)
# ---------------------------------------------------------------------------
QUERIES = [
    # exact keyword
    {"test_id": "kw-01", "category": "exact_keyword", "question": "Why did we choose Stripe instead of Paddle?",
     "expected_decision_ids": ["91b4aa2f-a02c-44c2-be89-10053f9d32f4"], "expected_answerable": True},
    {"test_id": "kw-02", "category": "exact_keyword", "question": "Why are we migrating the job queue from Redis Streams to pgmq?",
     "expected_decision_ids": ["f8aeac83-5ec7-4a05-914c-112bc85cf668"], "expected_answerable": True},
    {"test_id": "kw-03", "category": "exact_keyword", "question": "Why did we move the primary database to a multi-AZ RDS setup?",
     "expected_decision_ids": ["a992a87e-e964-4dec-822a-c2fda9269ba9"], "expected_answerable": True},
    {"test_id": "kw-04", "category": "exact_keyword", "question": "Why are we requiring SSO for all internal tools?",
     "expected_decision_ids": ["2c4e1793-7b17-4510-8b9a-64c8cd72f312"], "expected_answerable": True},
    # semantic paraphrase
    {"test_id": "para-01", "category": "semantic_paraphrase", "question": "What's our plan for the mobile app this quarter?",
     "expected_decision_ids": ["bb4cad80-ac94-4d50-b98d-397d0eeceffa"], "expected_answerable": True},
    {"test_id": "para-02", "category": "semantic_paraphrase", "question": "Are we keeping the downtown office space?",
     "expected_decision_ids": ["0c4ee9e7-30f0-434e-a94e-2207532fa7bf"], "expected_answerable": True},
    {"test_id": "para-03", "category": "semantic_paraphrase", "question": "What analytics tooling change did the data team make?",
     "expected_decision_ids": ["3c766c71-448d-44fb-8b30-6b6d7960ada0"], "expected_answerable": True},
    {"test_id": "para-04", "category": "semantic_paraphrase", "question": "What's happening with our Kubernetes rollout?",
     "expected_decision_ids": ["8473d874-f519-4e86-be71-12c26a5ba2d7"], "expected_answerable": True},
    # rationale
    {"test_id": "rat-01", "category": "rationale", "question": "Why did we raise the support SLA from 48 to 24 hours?",
     "expected_decision_ids": ["95652444-0666-4c51-8dbd-7048ccadbce8"], "expected_answerable": True},
    {"test_id": "rat-02", "category": "rationale", "question": "Why did we decide not to renew the office lease?",
     "expected_decision_ids": ["0c4ee9e7-30f0-434e-a94e-2207532fa7bf"], "expected_answerable": True},
    {"test_id": "rat-03", "category": "rationale", "question": "Why did we migrate off self-hosted Snowplow?",
     "expected_decision_ids": ["3c766c71-448d-44fb-8b30-6b6d7960ada0"], "expected_answerable": True},
    {"test_id": "rat-04", "category": "rationale", "question": "Why are we enforcing SSO on internal tools?",
     "expected_decision_ids": ["2c4e1793-7b17-4510-8b9a-64c8cd72f312"], "expected_answerable": True},
    # actor / owner
    {"test_id": "actor-01", "category": "actor_owner", "question": "Who is responsible for setting up nightly database backups?",
     "expected_decision_ids": ["47a5d5f4-7cc2-4a5b-81e2-b968f03279cf"], "expected_answerable": True},
    {"test_id": "actor-02", "category": "actor_owner", "question": "Who will build the self-serve analytics dashboard for sales?",
     "expected_decision_ids": ["cde053c4-0972-4ea7-8b1c-80003beb4cfa"], "expected_answerable": True},
    {"test_id": "actor-03", "category": "actor_owner", "question": "Who decided to extend the offer to the backend engineer candidate?",
     "expected_decision_ids": ["8cc8888e-7701-43da-b210-18ad4c58027c"], "expected_answerable": True},
    # multi-decision
    {"test_id": "multi-01", "category": "multi_decision", "question": "What infrastructure decisions have we made recently?",
     "expected_decision_ids": ["a992a87e-e964-4dec-822a-c2fda9269ba9", "8473d874-f519-4e86-be71-12c26a5ba2d7", "47a5d5f4-7cc2-4a5b-81e2-b968f03279cf"],
     "expected_answerable": True},
    {"test_id": "multi-02", "category": "multi_decision", "question": "What security-related decisions and blockers do we have?",
     "expected_decision_ids": ["2c4e1793-7b17-4510-8b9a-64c8cd72f312", "b006a28d-723d-4319-b84b-a60485059772"],
     "excluded_decision_ids": ["fc7ea5af-5817-4cf3-859f-9eaa3d4b8fdf"], "expected_answerable": True},
    {"test_id": "multi-03", "category": "multi_decision", "question": "What blockers are currently affecting different teams?",
     "expected_decision_ids": ["6b1ee81d-793c-4525-9b5a-b5cc3f84ec69", "b006a28d-723d-4319-b84b-a60485059772",
                               "6d741b8c-3a55-499b-ad8b-f1f8c0d847e1", "facdb6a7-2bde-4324-b365-114c81f1c8c8",
                               "a9b1bbbf-6ff0-4c91-b718-89a307273e52"],
     "expected_answerable": True},
    # permission-restricted
    {"test_id": "perm-01", "category": "permission_restricted", "question": "What did we decide about the password rotation policy?",
     "expected_decision_ids": [], "excluded_decision_ids": ["fc7ea5af-5817-4cf3-859f-9eaa3d4b8fdf"], "expected_answerable": False},
    {"test_id": "perm-02", "category": "permission_restricted", "question": "Why is finance switching AWS billing to annual?",
     "expected_decision_ids": [], "excluded_decision_ids": ["e47da747-a0f1-4bfd-80c8-3fc10ada3f0a"], "expected_answerable": False},
    {"test_id": "perm-03", "category": "permission_restricted", "question": "What did legal decide about data retention?",
     "expected_decision_ids": [], "excluded_decision_ids": ["647253df-bd84-489b-95e9-4ea017a53742"], "expected_answerable": False},
    # negative / no-answer
    {"test_id": "neg-01", "category": "no_answer", "question": "Did we decide to acquire any companies this year?",
     "expected_decision_ids": [], "expected_answerable": False},
    {"test_id": "neg-02", "category": "no_answer", "question": "What's our policy on unlimited vacation days?",
     "expected_decision_ids": [], "expected_answerable": False},
    {"test_id": "neg-03", "category": "no_answer", "question": "Have we decided to switch our cloud provider away from AWS?",
     "expected_decision_ids": [], "expected_answerable": False},
    {"test_id": "neg-04", "category": "no_answer", "question": "What did we decide about opening a new office in Europe?",
     "expected_decision_ids": [], "expected_answerable": False},
]

assert len(QUERIES) == 25, f"expected exactly 25 queries, got {len(QUERIES)}"


def _evaluate_query(q: dict, response_json: dict, wall_ms: float) -> dict:
    citations = response_json.get("citations", [])
    cited_ids = [c["decision_id"] for c in citations]
    answer = response_json.get("answer", "")
    expected = q["expected_decision_ids"]
    excluded = q.get("excluded_decision_ids", [])

    excluded_leak = any(x in cited_ids or x in answer for x in excluded)

    if q["expected_answerable"]:
        if q["category"] == "multi_decision":
            hit_count = sum(1 for e in expected if e in cited_ids)
            passed = hit_count == len(expected) and not excluded_leak
            reason = None if passed else (
                f"only {hit_count}/{len(expected)} expected decisions cited"
                if hit_count < len(expected) else "excluded decision leaked into citations/answer"
            )
        else:
            passed = any(e in cited_ids for e in expected) and not excluded_leak
            reason = None if passed else "expected decision not found in citations"
    else:
        # permission_restricted or no_answer: must be unanswered, no citations, no leak
        passed = (len(citations) == 0) and not excluded_leak
        reason = None if passed else (
            "restricted/absent decision leaked into citations or answer" if (excluded_leak or citations)
            else "unexpected citations present"
        )

    # rank of first expected id, by citation decision_number (1-indexed)
    rank = None
    for c in sorted(citations, key=lambda c: c["decision_number"]):
        if c["decision_id"] in expected:
            rank = c["decision_number"]
            break

    return {
        "test_id": q["test_id"],
        "category": q["category"],
        "question": q["question"],
        "expected_decision_ids": expected,
        "excluded_decision_ids": excluded,
        "retrieved_decision_ids": cited_ids,
        "retrieved_ranking": [{"decision_number": c["decision_number"], "decision_id": c["decision_id"],
                                "confidence": c["confidence"]} for c in citations],
        "first_expected_rank": rank,
        "generated_answer": answer,
        "citations": citations,
        "metadata": response_json.get("metadata", {}),
        "wall_clock_ms": round(wall_ms, 1),
        "expected_answerable": q["expected_answerable"],
        "status": "PASS" if passed else "FAIL",
        "failure_reason": reason,
    }


def main() -> None:
    token = issue_tenant_jwt(user_id="stage2-eval-user", tenant_id=TENANT_ID, role="member")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    results = []
    print(f"Running {len(QUERIES)} Stage 2 queries against {BASE_URL}/search (sequential, 1 call each)\n")

    with httpx.Client(timeout=30.0) as client:
        for i, q in enumerate(QUERIES, start=1):
            print(f"[{i}/{len(QUERIES)}] {q['test_id']} ({q['category']}): {q['question']}")
            start = time.perf_counter()
            try:
                resp = client.post(f"{BASE_URL}/search", headers=headers, json={"question": q["question"]})
                wall_ms = (time.perf_counter() - start) * 1000
                resp.raise_for_status()
                record = _evaluate_query(q, resp.json(), wall_ms)
            except Exception as exc:  # record failure, continue to next query — no retry
                wall_ms = (time.perf_counter() - start) * 1000
                record = {
                    "test_id": q["test_id"], "category": q["category"], "question": q["question"],
                    "expected_decision_ids": q["expected_decision_ids"],
                    "retrieved_decision_ids": [], "retrieved_ranking": [], "first_expected_rank": None,
                    "generated_answer": None, "citations": [], "metadata": {},
                    "wall_clock_ms": round(wall_ms, 1), "expected_answerable": q["expected_answerable"],
                    "status": "ERROR", "failure_reason": f"{type(exc).__name__}: {exc}",
                }
            print(f"  -> {record['status']}"
                  + (f" ({record['failure_reason']})" if record.get("failure_reason") else "")
                  + f"  latency={record['wall_clock_ms']}ms")
            results.append(record)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_file = RESULTS_DIR / f"stage2_results_{ts}.json"
    out_file.write_text(json.dumps(results, indent=2))
    print(f"\nRaw results written to {out_file}")
    print(f"RESULTS_FILE={out_file}")


if __name__ == "__main__":
    main()
