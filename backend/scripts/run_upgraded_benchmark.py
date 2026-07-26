"""
Upgraded-RAG-pipeline benchmark runner.

Calls the real, unmocked application service functions directly, in the
exact same sequence modules.search.service.search() calls them, against
the live DB/Claude/Voyage (no HTTP layer, no mocks) - this is necessary
because the per-stage instrumentation this benchmark needs (candidates
before rerank, authorized candidates, rerank scores, per-stage latency,
entities/keywords) is deliberately NOT exposed by the /search API
response (API contract is frozen for this validation task), so it can
only be captured by instrumenting the pipeline stages directly.

permission_scopes=[] matches real production behavior: resolve_permission_
scopes(ctx) always returns [] today (no per-user scope source exists yet),
exactly what the router passes for any authenticated caller.

Bypasses the /search rate limiter by design (that limiter is a FastAPI
route dependency, never reached when calling service functions directly)
- this is calling the actual application services, not hitting the HTTP
endpoint repeatedly, so there is no rate-limit concern to manage here.

Usage:
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/run_upgraded_benchmark.py
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import datetime, timezone
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
from database.pool import init_db_pool
from modules.answering.prompt_builder import REFUSAL_TEXT
from modules.answering.service import generate_answer
from modules.context.schemas import AuthorizedDecisionInput
from modules.context.service import build_context
from modules.permissions.service import filter_accessible_decisions
from modules.query_understanding.schemas import NULL_QUERY_ANALYSIS
from modules.query_understanding.service import QueryAnalysisError, analyze_query
from modules.retrieval.reranking.cross_encoder import rerank
from modules.retrieval.vector.schemas import DEFAULT_CANDIDATE_K, RetrievalMatch
from modules.retrieval.vector.service import search as vector_search
from modules.search.service import (
    MULTI_DOCUMENT_MIN_TOP_K,
    RERANK_MIN_TOP_K,
    _build_citations,
    _to_context_input,
)

CORPUS_DIR = SRC_DIR / "evaluation" / "corpus_v2"
TENANT_ID = "13bcd0fa-1ed9-4634-93c7-278ba97ec658"
PERMISSION_SCOPES: list[str] = []  # matches resolve_permission_scopes(ctx) production behavior
DEFAULT_TOP_K = 5
MAX_TOP_K = 50

OUTDIR = Path(open("/tmp/upgraded_rag_outdir.txt").read().strip())
OUTDIR = BACKEND_DIR / OUTDIR if not OUTDIR.is_absolute() else OUTDIR

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


def excluded_leak(cited_ids: list[str], answer: str, excluded: list[str]) -> bool:
    return any(x in cited_ids or x in answer for x in excluded)


async def run_one_query(pool: asyncpg.Pool, q: dict) -> dict:
    question = q["question"]
    t_start = time.perf_counter()
    stage_latency = {}

    # --- 1. query understanding ---
    t0 = time.perf_counter()
    query_understanding_failed_open = False
    try:
        analysis = await analyze_query(question)
    except QueryAnalysisError:
        analysis = NULL_QUERY_ANALYSIS
        query_understanding_failed_open = True
    stage_latency["query_understanding_ms"] = (time.perf_counter() - t0) * 1000

    effective_top_k = max(DEFAULT_TOP_K, RERANK_MIN_TOP_K)
    if analysis.is_multi_document:
        effective_top_k = min(MAX_TOP_K, max(effective_top_k, MULTI_DOCUMENT_MIN_TOP_K))
    candidate_k = max(DEFAULT_CANDIDATE_K, effective_top_k * 2)

    # --- 2. retrieval ---
    t0 = time.perf_counter()
    candidates, _dim = await vector_search(
        pool, TENANT_ID, question, top_k=effective_top_k,
        candidate_k=candidate_k,
        embedding_query=question,
        keyword_query=analysis.keyword_search_query,
    )
    stage_latency["retrieval_ms"] = (time.perf_counter() - t0) * 1000
    candidate_ids_pre_rerank = [str(m.decision_id) for m in candidates]

    # --- 3. permission filter ---
    t0 = time.perf_counter()
    authorized = filter_accessible_decisions(PERMISSION_SCOPES, candidates)
    stage_latency["permission_filter_ms"] = (time.perf_counter() - t0) * 1000
    authorized_ids = [str(m.decision_id) for m in authorized]

    # --- 4. rerank ---
    t0 = time.perf_counter()
    reranked = rerank(question, authorized, top_k=effective_top_k, entities=analysis.entities)
    stage_latency["reranking_ms"] = (time.perf_counter() - t0) * 1000
    reranking_failed_open = bool(reranked) and all(m.rerank_score is None for m in reranked)
    reranked_ids = [str(m.decision_id) for m in reranked]
    rerank_scores = [m.rerank_score for m in reranked]

    # security check: reranking must never introduce an id absent from authorized
    leaked_by_rerank = [rid for rid in reranked_ids if rid not in set(authorized_ids)]

    # --- 5. context + answer ---
    context_result = build_context([_to_context_input(m) for m in reranked])
    t0 = time.perf_counter()
    answer_result = await generate_answer(question, context_result.context, analysis)
    stage_latency["answer_generation_ms"] = (time.perf_counter() - t0) * 1000

    citations = _build_citations(answer_result.citations, reranked)
    cited_ids = [str(c.decision_id) for c in citations]

    total_ms = (time.perf_counter() - t_start) * 1000
    is_refusal = answer_result.answer == REFUSAL_TEXT

    # security check: citations must only reference ids that were authorized
    citation_not_authorized = [cid for cid in cited_ids if cid not in set(authorized_ids)]
    # security check: excluded (restricted-for-this-query) ids must never leak
    excl = q["excluded_decision_ids"]
    leaked = excluded_leak(cited_ids, answer_result.answer, excl)

    # --- scoring (identical logic across the whole exercise) ---
    expected = q["expected_decision_ids"]
    if q["expected_answerable"]:
        if q["is_multi"]:
            hit_count = sum(1 for e in expected if e in cited_ids)
            decision_level_recall = hit_count / len(expected) if expected else None
            passed = hit_count == len(expected) and not leaked
            reason = None if passed else f"{hit_count}/{len(expected)} expected cited" + (" + leak" if leaked else "")
        else:
            decision_level_recall = None
            passed = any(e in cited_ids for e in expected) and not leaked
            reason = None if passed else "expected decision not cited" + (" + leak" if leaked else "")
    else:
        decision_level_recall = None
        if excl:
            passed = not leaked
            reason = None if passed else "excluded decision leaked"
        else:
            passed = (len(citations) == 0) and not leaked
            reason = None if passed else "unexpected citation(s) on a no-answer query"

    rank = None
    for c in sorted(citations, key=lambda c: c.decision_number):
        if str(c.decision_id) in expected:
            rank = c.decision_number
            break

    return {
        "query_id": q["query_id"], "suite": q["suite"], "segment": q["segment"],
        "question": question,
        "question_type": analysis.question_type.value,
        "is_multi_document": analysis.is_multi_document,
        "entities": analysis.entities, "keywords": analysis.keywords,
        "rewritten_query": analysis.rewritten_query,
        "expected_decision_ids": expected, "excluded_decision_ids": excl,
        "candidate_ids_pre_rerank": candidate_ids_pre_rerank,
        "authorized_candidate_ids": authorized_ids,
        "reranked_decision_ids": reranked_ids,
        "rerank_scores": rerank_scores,
        "answer": answer_result.answer, "reasoning": answer_result.reasoning,
        "confidence": answer_result.confidence, "citations": cited_ids,
        "sufficient_evidence": answer_result.sufficient_evidence,
        "is_refusal": is_refusal,
        "first_expected_rank": rank, "decision_level_recall": decision_level_recall,
        "expected_answerable": q["expected_answerable"], "is_multi": q["is_multi"],
        "stage_latency_ms": stage_latency, "total_latency_ms": total_ms,
        "query_understanding_failed_open": query_understanding_failed_open,
        "reranking_failed_open": reranking_failed_open,
        "security_leaked_excluded": leaked,
        "security_rerank_introduced_unauthorized": leaked_by_rerank,
        "security_citation_not_authorized": citation_not_authorized,
        "status": "PASS" if passed else "FAIL",
        "failure_reason": reason,
    }


async def main():
    config = get_app_database_config()
    pool = await asyncpg.create_pool(dsn=config.dsn, min_size=2, max_size=8, statement_cache_size=0)
    await init_db_pool(pool)

    queries = load_queries()
    results = []
    print(f"Running {len(queries)} queries through the real upgraded pipeline (direct service calls)\n")

    try:
        for i, q in enumerate(queries, start=1):
            t0 = time.perf_counter()
            try:
                record = await run_one_query(pool, q)
            except Exception as exc:
                record = {
                    "query_id": q["query_id"], "suite": q["suite"], "segment": q["segment"],
                    "question": q["question"], "status": "ERROR",
                    "error": f"{type(exc).__name__}: {exc}",
                    "total_latency_ms": (time.perf_counter() - t0) * 1000,
                    "expected_answerable": q["expected_answerable"], "is_multi": q["is_multi"],
                    "expected_decision_ids": q["expected_decision_ids"],
                    "excluded_decision_ids": q["excluded_decision_ids"],
                }
                print(f"[{i}/{len(queries)}] {q['query_id']}: ERROR - {record['error']}")
            else:
                print(f"[{i}/{len(queries)}] {q['query_id']}: {record['status']}  "
                      f"total={record['total_latency_ms']:.0f}ms  refusal={record.get('is_refusal')}")
            results.append(record)

        OUTDIR.mkdir(parents=True, exist_ok=True)
        (OUTDIR / "per_query_results.jsonl").write_text(
            "\n".join(json.dumps(r) for r in results) + "\n"
        )
        (OUTDIR / "per_query_results.json").write_text(json.dumps(results, indent=2))
        print(f"\nWritten to {OUTDIR}")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
