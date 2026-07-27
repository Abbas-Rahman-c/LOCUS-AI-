from __future__ import annotations
import json
import statistics
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parents[1] / "src" / "evaluation" / "results_v2"

FILES = {
    "semantic_only": sorted(RESULTS_DIR.glob("final_semantic_only_*.json"))[-1],
    "keyword_only": sorted(RESULTS_DIR.glob("final_keyword_only_*.json"))[-1],
    "hybrid_rrf": sorted(RESULTS_DIR.glob("final_hybrid_rrf_*.json"))[-1],
}

SEGMENTS = ["regression", "keyword_favored", "semantic_favored", "hybrid_favored",
            "identifier_lookup", "entity_lookup", "near_duplicate", "permission", "no_answer"]


def excluded_leak(rec):
    cited = rec["retrieved_decision_ids"]
    answer = rec.get("generated_answer") or ""
    return any(x in cited or x in answer for x in rec["excluded_decision_ids"])


def is_permission_query(rec):
    return not rec["expected_answerable"] and bool(rec["excluded_decision_ids"])


def is_no_answer_query(rec):
    return not rec["expected_answerable"] and not rec["excluded_decision_ids"]


def recall_at_k(records, k):
    pool = [r for r in records if r["expected_answerable"]]
    if not pool:
        return None
    hits = sum(1 for r in pool if r["first_expected_rank"] is not None and r["first_expected_rank"] <= k)
    return hits / len(pool)


def mrr(records):
    pool = [r for r in records if r["expected_answerable"]]
    if not pool:
        return None
    return sum((1 / r["first_expected_rank"]) if r["first_expected_rank"] else 0 for r in pool) / len(pool)


def citation_precision_recall(records):
    precisions, recalls = [], []
    for r in records:
        if not r["expected_answerable"] or not r["expected_decision_ids"]:
            continue
        cited = set(r["retrieved_decision_ids"])
        expected = set(r["expected_decision_ids"])
        if cited:
            precisions.append(len(cited & expected) / len(cited))
        recalls.append(len(cited & expected) / len(expected))
    p = statistics.mean(precisions) if precisions else None
    rc = statistics.mean(recalls) if recalls else None
    return p, rc


def multi_accuracy(records):
    pool = [r for r in records if r["is_multi"]]
    if not pool:
        return None, None
    strict = sum(1 for r in pool if r["status"] == "PASS") / len(pool)
    decision_level = statistics.mean(
        r["decision_level_recall"] if r["decision_level_recall"] is not None else 0 for r in pool
    )
    return strict, decision_level


def permission_accuracy(records):
    pool = [r for r in records if is_permission_query(r)]
    if not pool:
        return None, pool
    acc = sum(1 for r in pool if not excluded_leak(r)) / len(pool)
    return acc, pool


def no_answer_accuracy(records):
    pool = [r for r in records if is_no_answer_query(r)]
    if not pool:
        return None, pool
    acc = sum(1 for r in pool if r["status"] == "PASS") / len(pool)
    return acc, pool


def latency_stats(records):
    lat = sorted(r["wall_clock_ms"] for r in records)
    avg = statistics.mean(lat)
    p95_idx = min(len(lat) - 1, int(round(0.95 * (len(lat) - 1))))
    return avg, lat[p95_idx]


def overall_metrics(records):
    r1, r3, r5 = recall_at_k(records, 1), recall_at_k(records, 3), recall_at_k(records, 5)
    m = mrr(records)
    cp, cr = citation_precision_recall(records)
    strict_multi, decision_multi = multi_accuracy(records)
    perm_acc, perm_pool = permission_accuracy(records)
    noans_acc, noans_pool = no_answer_accuracy(records)
    avg_lat, p95_lat = latency_stats(records)
    return {
        "recall_at_1": r1, "recall_at_3": r3, "recall_at_5": r5, "mrr": m,
        "citation_precision": cp, "citation_recall": cr,
        "strict_multi_accuracy": strict_multi, "decision_level_multi_accuracy": decision_multi,
        "permission_accuracy": perm_acc, "permission_pool_size": len(perm_pool),
        "no_answer_accuracy": noans_acc, "no_answer_pool_size": len(noans_pool),
        "avg_latency_ms": avg_lat, "p95_latency_ms": p95_lat,
        "n_queries": len(records), "n_pass": sum(1 for r in records if r["status"] == "PASS"),
        "n_fail": sum(1 for r in records if r["status"] == "FAIL"),
    }


def main():
    data = {mode: json.loads(path.read_text()) for mode, path in FILES.items()}

    report = {"files": {k: str(v) for k, v in FILES.items()}, "overall": {}, "by_segment": {}}

    for mode, records in data.items():
        report["overall"][mode] = overall_metrics(records)

    for seg in SEGMENTS:
        report["by_segment"][seg] = {}
        for mode, records in data.items():
            seg_records = [r for r in records if r["segment"] == seg]
            report["by_segment"][seg][mode] = overall_metrics(seg_records) if seg_records else None
            report["by_segment"][seg]["_n"] = len(seg_records)

    # per-query cross-mode table
    query_ids = [r["query_id"] for r in data["semantic_only"]]
    cross = {}
    for qid in query_ids:
        cross[qid] = {}
        for mode, records in data.items():
            rec = next(r for r in records if r["query_id"] == qid)
            cross[qid][mode] = {
                "status": rec["status"], "first_expected_rank": rec["first_expected_rank"],
                "retrieved": rec["retrieved_decision_ids"], "expected": rec["expected_decision_ids"],
                "excluded": rec["excluded_decision_ids"], "segment": rec["segment"],
                "expected_answerable": rec["expected_answerable"], "is_multi": rec["is_multi"],
                "excluded_leak": excluded_leak(rec), "latency_ms": rec["wall_clock_ms"],
                "question": rec["question"],
            }
    report["cross_mode"] = cross

    Path("/tmp/final_benchmark_report.json").write_text(json.dumps(report, indent=2, default=str))
    print("Written to /tmp/final_benchmark_report.json")

    # quick console summary
    for mode in ["semantic_only", "keyword_only", "hybrid_rrf"]:
        m = report["overall"][mode]
        print(f"\n{mode}: R@1={m['recall_at_1']:.3f} R@3={m['recall_at_3']:.3f} R@5={m['recall_at_5']:.3f} "
              f"MRR={m['mrr']:.3f} CP={m['citation_precision']:.3f} CR={m['citation_recall']:.3f} "
              f"perm_acc={m['permission_accuracy']:.3f} noans_acc={m['no_answer_accuracy']:.3f} "
              f"avg_lat={m['avg_latency_ms']:.0f}ms p95={m['p95_latency_ms']:.0f}ms "
              f"pass={m['n_pass']}/60")


if __name__ == "__main__":
    main()
