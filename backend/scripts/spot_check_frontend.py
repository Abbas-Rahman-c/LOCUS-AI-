"""Spot-check 8 frontend-ready scenarios via the real HTTP /search endpoint."""
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

from modules.auth.service import issue_tenant_jwt

TENANT_ID = "13bcd0fa-1ed9-4634-93c7-278ba97ec658"
OUTDIR = Path(open("/tmp/upgraded_rag_outdir.txt").read().strip())
OUTDIR = BACKEND_DIR / OUTDIR if not OUTDIR.is_absolute() else OUTDIR

SCENARIOS = [
    ("normal_decision_question", "Why did we choose Stripe instead of Paddle?"),
    ("why_question", "Why are we migrating the job queue from Redis Streams to pgmq?"),
    ("entity_person_lookup", "What has Priya Chen worked on?"),
    ("ticket_id_lookup", "What's the update on INFRA-751?"),
    ("filename_lookup", "What does rollout_plan_v1.xlsx cover?"),
    ("no_answer_question", "Did we decide to acquire any companies this year?"),
    ("unauthorized_restricted_question", "What did we decide about the password rotation policy?"),
    ("multi_decision_summary", "What security decisions have we made recently?"),
]

token = issue_tenant_jwt(user_id="spotcheck", tenant_id=TENANT_ID, role="member")
results = []
with httpx.Client(timeout=60.0) as client:
    for name, question in SCENARIOS:
        t0 = time.perf_counter()
        try:
            r = client.post("http://localhost:8000/search",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"question": question})
            wall_ms = (time.perf_counter() - t0) * 1000
            body = r.json()
            record = {
                "scenario": name, "question": question, "http_status": r.status_code,
                "answer": body.get("answer"), "citations": body.get("citations"),
                "reasoning": body.get("reasoning"), "confidence": body.get("confidence"),
                "metadata": body.get("metadata"), "total_latency_ms": round(wall_ms, 1),
            }
        except Exception as exc:
            wall_ms = (time.perf_counter() - t0) * 1000
            record = {"scenario": name, "question": question, "http_status": None,
                       "error": f"{type(exc).__name__}: {exc}", "total_latency_ms": round(wall_ms, 1)}
        print(f"[{name}] status={record.get('http_status')} latency={record['total_latency_ms']}ms")
        results.append(record)

(OUTDIR / "spot_check_results.json").write_text(json.dumps(results, indent=2))
print(f"\nWritten to {OUTDIR / 'spot_check_results.json'}")
