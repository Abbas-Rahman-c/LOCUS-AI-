"""
Bounded, one-shot retry of the Stage 2 queries that failed with HTTP 429
(rate-limited before reaching the search service — zero Voyage/Claude calls
were made for them). Retries each exactly once, sequentially, no
concurrency, and merges the result back into the original results file.

This is the narrow "genuine transient failure" retry — it does not touch
any query that already got a real PASS/FAIL answer from the pipeline.

Usage:
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/retry_stage2_failed.py <results_file.json>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import httpx
from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_stage2_eval import QUERIES, TENANT_ID, BASE_URL, _evaluate_query  # noqa: E402
from modules.auth.service import issue_tenant_jwt


def main() -> None:
    results_file = Path(sys.argv[1])
    results = json.loads(results_file.read_text())
    queries_by_id = {q["test_id"]: q for q in QUERIES}

    to_retry = [r for r in results if r["status"] == "ERROR"]
    print(f"Retrying {len(to_retry)} rate-limited queries, exactly once each, sequentially.")

    token = issue_tenant_jwt(user_id="stage2-eval-user", tenant_id=TENANT_ID, role="member")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    with httpx.Client(timeout=30.0) as client:
        for r in to_retry:
            q = queries_by_id[r["test_id"]]
            print(f"Retrying {q['test_id']}: {q['question']}")
            start = time.perf_counter()
            try:
                resp = client.post(f"{BASE_URL}/search", headers=headers, json={"question": q["question"]})
                wall_ms = (time.perf_counter() - start) * 1000
                resp.raise_for_status()
                new_record = _evaluate_query(q, resp.json(), wall_ms)
            except Exception as exc:
                wall_ms = (time.perf_counter() - start) * 1000
                new_record = {
                    "test_id": q["test_id"], "category": q["category"], "question": q["question"],
                    "expected_decision_ids": q["expected_decision_ids"],
                    "retrieved_decision_ids": [], "retrieved_ranking": [], "first_expected_rank": None,
                    "generated_answer": None, "citations": [], "metadata": {},
                    "wall_clock_ms": round(wall_ms, 1), "expected_answerable": q["expected_answerable"],
                    "status": "ERROR", "failure_reason": f"{type(exc).__name__}: {exc}",
                }
            print(f"  -> {new_record['status']}"
                  + (f" ({new_record['failure_reason']})" if new_record.get("failure_reason") else "")
                  + f"  latency={new_record['wall_clock_ms']}ms")

            for i, r2 in enumerate(results):
                if r2["test_id"] == q["test_id"]:
                    results[i] = new_record
                    break

    results_file.write_text(json.dumps(results, indent=2))
    print(f"\nMerged results written back to {results_file}")


if __name__ == "__main__":
    main()
