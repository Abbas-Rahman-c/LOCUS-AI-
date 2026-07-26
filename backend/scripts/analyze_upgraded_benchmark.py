from __future__ import annotations
import json
import statistics
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTDIR = Path(open("/tmp/upgraded_rag_fixed_outdir.txt").read().strip())
OUTDIR = BACKEND_DIR / OUTDIR if not OUTDIR.is_absolute() else OUTDIR

BASELINE_FILE = BACKEND_DIR / "src/evaluation/results_v2/final_semantic_only_20260726T000244Z.json"

BASELINE_PUBLISHED = {
    "recall_at_1": 0.489, "recall_at_3": 0.644, "recall_at_5": 0.711, "mrr": 0.574,
    "citation_precision": 0.507, "citation_recall": 0.636, "permission_accuracy": 1.000,
    "no_answer_accuracy": 0.333, "avg_latency_ms": 2888, "n_pass": 37,
}

SEGMENTS = ["regression", "keyword_favored", "semantic_favored", "hybrid_favored",
            "identifier_lookup", "entity_lookup", "near_duplicate", "permission", "no_answer"]


def is_permission_query(r):
    return not r["expected_answerable"] and bool(r.get("excluded_decision_ids"))


def is_no_answer_query(r):
    return not r["expected_answerable"] and not r.get("excluded_decision_ids")


def recall_at_k(records, k, rank_key="first_expected_rank"):
    pool = [r for r in records if r["expected_answerable"]]
    if not pool:
        return None
    hits = sum(1 for r in pool if r.get(rank_key) is not None and r[rank_key] <= k)
    return hits / len(pool)


def mrr(records, rank_key="first_expected_rank"):
    pool = [r for r in records if r["expected_answerable"]]
    if not pool:
        return None
    return sum((1 / r[rank_key]) if r.get(rank_key) else 0 for r in pool) / len(pool)


def citation_pr(records, cited_key="citations"):
    precisions, recalls = [], []
    for r in records:
        if not r["expected_answerable"] or not r.get("expected_decision_ids"):
            continue
        cited = set(r.get(cited_key) or [])
        expected = set(r["expected_decision_ids"])
        if cited:
            precisions.append(len(cited & expected) / len(cited))
        recalls.append(len(cited & expected) / len(expected))
    return (statistics.mean(precisions) if precisions else None,
            statistics.mean(recalls) if recalls else None)


def latency_stats(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None, None, None
    avg = statistics.mean(vals)
    med = statistics.median(vals)
    p95 = vals[min(len(vals) - 1, int(round(0.95 * (len(vals) - 1))))]
    return avg, med, p95


def overall_metrics_upgraded(records):
    completed = [r for r in records if r["status"] != "ERROR"]
    r1, r3, r5 = recall_at_k(completed, 1), recall_at_k(completed, 3), recall_at_k(completed, 5)
    m = mrr(completed)
    cp, cr = citation_pr(completed)
    perm_pool = [r for r in completed if is_permission_query(r)]
    perm_acc = sum(1 for r in perm_pool if r["status"] == "PASS") / len(perm_pool) if perm_pool else None
    noans_pool = [r for r in completed if is_no_answer_query(r)]
    noans_acc = sum(1 for r in noans_pool if r["status"] == "PASS") / len(noans_pool) if noans_pool else None
    entity_pool = [r for r in completed if r["segment"] == "entity_lookup"]
    entity_pass = sum(1 for r in entity_pool if r["status"] == "PASS") / len(entity_pool) if entity_pool else None
    multi_pool = [r for r in completed if r.get("is_multi_document")]
    multi_pass = sum(1 for r in multi_pool if r["status"] == "PASS") / len(multi_pool) if multi_pool else None
    answerable_pool = [r for r in completed if r["expected_answerable"]]
    answerable_pass = sum(1 for r in answerable_pool if r["status"] == "PASS") / len(answerable_pool) if answerable_pool else None

    total_lat = [r["total_latency_ms"] for r in completed]
    avg_lat, med_lat, p95_lat = latency_stats(total_lat)

    stage_avgs = {}
    for stage in ["query_understanding_ms", "retrieval_ms", "permission_filter_ms", "reranking_ms", "answer_generation_ms"]:
        vals = [r["stage_latency_ms"][stage] for r in completed if r.get("stage_latency_ms")]
        stage_avgs[stage] = statistics.mean(vals) if vals else None

    qu_failed_open = sum(1 for r in completed if r.get("query_understanding_failed_open"))
    rerank_failed_open = sum(1 for r in completed if r.get("reranking_failed_open"))

    claude_calls = sum(2 if not r.get("query_understanding_failed_open") else 1 for r in completed)
    voyage_calls = len(completed)  # hybrid_rrf mode: always embeds once per query

    return {
        "n_total": len(records), "n_completed": len(completed), "n_errors": len(records) - len(completed),
        "recall_at_1": r1, "recall_at_3": r3, "recall_at_5": r5, "mrr": m,
        "citation_precision": cp, "citation_recall": cr,
        "permission_accuracy": perm_acc, "permission_pool_size": len(perm_pool),
        "no_answer_accuracy": noans_acc, "no_answer_pool_size": len(noans_pool),
        "entity_query_pass_rate": entity_pass, "entity_pool_size": len(entity_pool),
        "multi_document_pass_rate": multi_pass, "multi_document_pool_size": len(multi_pool),
        "answerable_query_pass_rate": answerable_pass,
        "n_pass": sum(1 for r in completed if r["status"] == "PASS"),
        "n_fail": sum(1 for r in completed if r["status"] == "FAIL"),
        "avg_latency_ms": avg_lat, "median_latency_ms": med_lat, "p95_latency_ms": p95_lat,
        "stage_avg_latency_ms": stage_avgs,
        "claude_call_count": claude_calls, "voyage_call_count": voyage_calls,
        "query_understanding_failed_open_count": qu_failed_open,
        "reranking_failed_open_count": rerank_failed_open,
    }


def security_checks(records):
    findings = []
    for r in records:
        if r.get("status") == "ERROR":
            continue
        if r.get("security_rerank_introduced_unauthorized"):
            findings.append(("rerank_introduced_unauthorized", r["query_id"], r["security_rerank_introduced_unauthorized"]))
        if r.get("security_citation_not_authorized"):
            findings.append(("citation_not_authorized", r["query_id"], r["security_citation_not_authorized"]))
        if r.get("security_leaked_excluded"):
            findings.append(("excluded_decision_leaked", r["query_id"], r.get("excluded_decision_ids")))
        if r.get("is_refusal") and r.get("citations"):
            findings.append(("refusal_with_nonzero_citations", r["query_id"], r["citations"]))
    return findings


def main():
    upgraded = json.loads((OUTDIR / "per_query_results.json").read_text())
    baseline = json.loads(BASELINE_FILE.read_text())

    upgraded_metrics = overall_metrics_upgraded(upgraded)
    sec_findings = security_checks(upgraded)

    # per-query improved/regressed/unchanged (status-based)
    baseline_by_id = {r["query_id"]: r for r in baseline}
    improved, regressed, unchanged, new_queries = [], [], [], []
    for r in upgraded:
        qid = r["query_id"]
        if qid in baseline_by_id:
            old_status = baseline_by_id[qid]["status"]
            new_status = r["status"]
            if old_status == "FAIL" and new_status == "PASS":
                improved.append(qid)
            elif old_status == "PASS" and new_status in ("FAIL", "ERROR"):
                regressed.append(qid)
            else:
                unchanged.append(qid)
        else:
            new_queries.append(qid)

    segment_metrics = {}
    for seg in SEGMENTS:
        seg_records = [r for r in upgraded if r["segment"] == seg and r["status"] != "ERROR"]
        segment_metrics[seg] = {"n": len(seg_records), **overall_metrics_upgraded(seg_records)} if seg_records else None

    report = {
        "upgraded_metrics": upgraded_metrics,
        "baseline_published": BASELINE_PUBLISHED,
        "security_findings": sec_findings,
        "comparison": {
            "improved_query_ids": improved, "regressed_query_ids": regressed,
            "unchanged_query_ids": unchanged, "new_query_ids_not_in_baseline": new_queries,
        },
        "segment_metrics": segment_metrics,
    }
    (OUTDIR / "benchmark_results.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(upgraded_metrics, indent=2, default=str))
    print("\nSECURITY FINDINGS:", sec_findings if sec_findings else "NONE")
    print("\nIMPROVED:", improved)
    print("REGRESSED:", regressed)
    print(f"UNCHANGED: {len(unchanged)} queries")


if __name__ == "__main__":
    main()
