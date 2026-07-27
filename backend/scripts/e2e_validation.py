"""
End-to-end validation test categories, run via the real /search HTTP
endpoint (the same endpoint the frontend would call, if it called one).
No mocks. Real Voyage/Claude/cross-encoder/DB.
"""
from __future__ import annotations
import json
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

import sys
sys.path.insert(0, str(BACKEND_DIR / "src"))
from modules.auth.service import issue_tenant_jwt

TENANT_ID = "13bcd0fa-1ed9-4634-93c7-278ba97ec658"
OUTFILE = BACKEND_DIR / "src" / "evaluation" / "e2e_validation_results.json"

TESTS = [
    ("T1a", "normal_decision", "Why did we move from Paddle to Stripe?"),
    ("T1b", "normal_decision", "Why did we choose PostgreSQL?"),
    ("T2a", "entity", "What decisions mention Marcus Webb?"),
    ("T2b", "entity", "What's the update on INFRA-751?"),
    ("T2c", "entity", "What did we decide about SOC2?"),
    ("T2d", "entity", "What did we decide about Stripe?"),
    ("T3a", "identifier", "What's the update on INFRA-751?"),
    ("T3b", "identifier", "What's the update on AUTH-204?"),
    ("T3c", "identifier", "What does invoice.pdf cover?"),
    ("T4a", "multi_document", "What billing decisions have we made?"),
    ("T4b", "multi_document", "Summarize authentication decisions."),
    ("T5a", "no_answer", "Did we open an office in Germany?"),
    ("T5b", "no_answer", "Who approved Project Apollo?"),
    ("T6a", "permission", "What did we decide about the password rotation policy?"),
]

token = issue_tenant_jwt(user_id="e2e-validation", tenant_id=TENANT_ID, role="member")
results = []

with httpx.Client(timeout=60.0) as client:
    for test_id, category, question in TESTS:
        t0 = time.perf_counter()
        try:
            r = client.post("http://localhost:8000/search",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"question": question})
            wall_ms = (time.perf_counter() - t0) * 1000
            body = r.json()
            record = {
                "test_id": test_id, "category": category, "question": question,
                "http_status": r.status_code, "answer": body.get("answer"),
                "citations": body.get("citations"), "reasoning": body.get("reasoning"),
                "confidence": body.get("confidence"), "metadata": body.get("metadata"),
                "total_latency_ms": round(wall_ms, 1),
            }
        except Exception as exc:
            record = {"test_id": test_id, "category": category, "question": question,
                       "http_status": None, "error": f"{type(exc).__name__}: {exc}",
                       "total_latency_ms": (time.perf_counter() - t0) * 1000}
        print(f"[{test_id}] {category}: status={record.get('http_status')} "
              f"latency={record['total_latency_ms']:.0f}ms citations={len(record.get('citations') or [])}")
        results.append(record)

    # Stress test: 10 consecutive questions, check stability + latency variance
    print("\n--- stress test: 10 consecutive questions ---")
    stress_questions = [
        "Why did we choose Stripe instead of Paddle?",
        "Why are we migrating the job queue from Redis Streams to pgmq?",
        "What did we decide about the password rotation policy?",
        "Did we decide to acquire any companies this year?",
        "What security decisions have we made recently?",
        "What has Priya Chen worked on?",
        "What's the update on INFRA-751?",
        "What did we decide about opening a new office in Europe?",
        "Why did we raise the support SLA from 48 to 24 hours?",
        "What analytics tooling change did the data team make?",
    ]
    stress_results = []
    for i, q in enumerate(stress_questions, start=1):
        t0 = time.perf_counter()
        try:
            r = client.post("http://localhost:8000/search",
                             headers={"Authorization": f"Bearer {token}"}, json={"question": q})
            wall_ms = (time.perf_counter() - t0) * 1000
            stress_results.append({"i": i, "question": q, "status": r.status_code, "latency_ms": round(wall_ms, 1)})
        except Exception as exc:
            wall_ms = (time.perf_counter() - t0) * 1000
            stress_results.append({"i": i, "question": q, "status": None,
                                    "error": f"{type(exc).__name__}: {exc}", "latency_ms": round(wall_ms, 1)})
        print(f"  [{i}/10] status={stress_results[-1]['status']} latency={stress_results[-1]['latency_ms']:.0f}ms")

(BACKEND_DIR / "src" / "evaluation").mkdir(parents=True, exist_ok=True)
OUTFILE.write_text(json.dumps({"tests": results, "stress_test": stress_results}, indent=2))
print(f"\nWritten to {OUTFILE}")
