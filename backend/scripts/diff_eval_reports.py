"""
Diffs two eval_report.json files -- this IS the prompt-tuning /
retrieval-parameter-optimization loop: run the real pipeline, change one
thing (a prompt line, RRF's k, the candidate pool multiplier, top_k), run
it again, diff the two reports, keep the change only if the diff is a net
win.

Usage:
    poetry run python scripts/diff_eval_reports.py baseline.json eval_report.json
    poetry run python scripts/diff_eval_reports.py baseline.json eval_report.json --per-example
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


_METRICS = [
    "recall_at_5",
    "recall_at_10",
    "hit_rate_at_5",
    "hit_rate_at_10",
    "mrr",
    "negative_hit_rate",
    "groundedness",
    "correctness",
    "citation_precision",
    "citation_recall",
    "mean_retrieval_latency_ms",
    "p95_retrieval_latency_ms",
]

# Metrics where a lower number is the improvement (everything else: higher is better).
_LOWER_IS_BETTER = {"negative_hit_rate", "mean_retrieval_latency_ms", "p95_retrieval_latency_ms"}


def _print_aggregate_diff(before: dict, after: dict) -> None:
    print(f"{'metric':<24}{'before':>10}{'after':>10}{'delta':>10}")
    for metric in _METRICS:
        b = before["report"].get(metric)
        a = after["report"].get(metric)
        if b is None or a is None:
            print(f"{metric:<24}{'n/a' if b is None else b:>10}{'n/a' if a is None else a:>10}{'n/a':>10}")
            continue
        delta = a - b
        lower_is_better = metric in _LOWER_IS_BETTER
        if delta == 0:
            arrow = "flat"
        elif (delta < 0) == lower_is_better:
            arrow = "improved"
        else:
            arrow = "regressed"
        print(f"{metric:<24}{b:>10.3f}{a:>10.3f}{delta:>+10.3f}  {arrow}")

    n_errors_before = before["report"].get("n_errors", 0)
    n_errors_after = after["report"].get("n_errors", 0)
    if n_errors_before or n_errors_after:
        print(f"\nerrors: {n_errors_before} -> {n_errors_after}")


def _print_per_example_diff(before: dict, after: dict) -> None:
    before_by_id = {e["example_id"]: e for e in before["examples"]}
    after_by_id = {e["example_id"]: e for e in after["examples"]}

    print("\nPer-example movement (recall_at_10 / reciprocal_rank):")
    for example_id in sorted(set(before_by_id) | set(after_by_id)):
        b = before_by_id.get(example_id)
        a = after_by_id.get(example_id)
        if b is None or a is None:
            print(f"  {example_id}: only present in {'after' if b is None else 'before'} report")
            continue
        b_r10, a_r10 = b.get("recall_at_10"), a.get("recall_at_10")
        b_rr, a_rr = b.get("reciprocal_rank"), a.get("reciprocal_rank")
        if b_r10 == a_r10 and b_rr == a_rr:
            continue
        print(f"  {example_id} [{a.get('category')}]: recall_at_10 {b_r10} -> {a_r10}  |  RR {b_rr} -> {a_rr}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diff two eval_report.json files.")
    parser.add_argument("baseline", type=Path, help="Earlier eval_report.json (e.g. the mock-pipeline baseline).")
    parser.add_argument("candidate", type=Path, help="Newer eval_report.json to compare against baseline.")
    parser.add_argument("--per-example", action="store_true", help="Also print per-example movement.")
    args = parser.parse_args()

    before = _load(args.baseline)
    after = _load(args.candidate)

    print(f"Baseline: {args.baseline} (pipeline={before['report'].get('pipeline_name')})")
    print(f"Candidate: {args.candidate} (pipeline={after['report'].get('pipeline_name')})")
    print()
    _print_aggregate_diff(before, after)

    if args.per_example:
        _print_per_example_diff(before, after)


if __name__ == "__main__":
    main()
