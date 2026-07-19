"""
Writes eval_report.json (machine-readable, diffable) and eval_report.md
(human-readable) from an EvalReport + its PerExampleScore list.

scripts/diff_eval_reports.py reads eval_report.json back in -- that diff,
run before/after a prompt or retrieval-parameter change, IS the tuning
loop: this file's only job is making that diff possible (stable field
names, one JSON object, no timestamps mixed into the parts you'd want to
diff away).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from modules.retrieval.evaluation.metrics import EvalReport, PerExampleScore


def write_json_report(report: EvalReport, scores: list[PerExampleScore], path: str | Path) -> None:
    payload = {
        "report": asdict(report),
        "examples": [asdict(s) for s in scores],
    }
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def write_markdown_report(report: EvalReport, scores: list[PerExampleScore], path: str | Path) -> None:
    lines = [
        f"# RAG Evaluation Report -- {report.pipeline_name}",
        "",
        f"Generated: {report.generated_at}",
        f"Examples: {report.n_examples} (errors: {report.n_errors})  |  top_k: {report.top_k}",
        "",
        "## Aggregate metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Recall@5 | {_fmt(report.recall_at_5)} |",
        f"| Recall@10 | {_fmt(report.recall_at_10)} |",
        f"| Hit Rate@5 (retrieval accuracy) | {_fmt(report.hit_rate_at_5)} |",
        f"| Hit Rate@10 (retrieval accuracy) | {_fmt(report.hit_rate_at_10)} |",
        f"| MRR | {_fmt(report.mrr)} |",
        f"| Negative hit rate (false positives) | {_fmt(report.negative_hit_rate)} |",
        f"| Groundedness (LLM judge) | {_fmt(report.groundedness)} |",
        f"| Correctness (LLM judge) | {_fmt(report.correctness)} |",
        f"| Citation precision | {_fmt(report.citation_precision)} |",
        f"| Citation recall | {_fmt(report.citation_recall)} |",
        f"| Mean retrieval latency (ms) | {_fmt(report.mean_retrieval_latency_ms)} |",
        f"| P95 retrieval latency (ms) | {_fmt(report.p95_retrieval_latency_ms)} |",
        "",
        "## Category coverage",
        "",
        "| Category | Count |",
        "|---|---|",
    ]
    for category, count in sorted(report.category_coverage.items()):
        lines.append(f"| {category} | {count} |")

    lines += [
        "",
        "## Per-example detail",
        "",
        "| ID | Category | Recall@10 | RR | Neg FP | Groundedness | Correctness | Cite P | Cite R | Latency (ms) | Error |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in scores:
        lines.append(
            "| {id} | {cat} | {r10} | {rr} | {negfp} | {grd} | {corr} | {cp} | {cr} | {lat} | {err} |".format(
                id=row.example_id,
                cat=row.category,
                r10="-" if row.recall_at_10 is None else _fmt(row.recall_at_10),
                rr="-" if row.reciprocal_rank is None else _fmt(row.reciprocal_rank),
                negfp="-" if row.negative_false_positive is None else str(row.negative_false_positive),
                grd="-" if row.groundedness is None else _fmt(row.groundedness),
                corr="-" if row.correctness is None else _fmt(row.correctness),
                cp="-" if row.citation_precision is None else _fmt(row.citation_precision),
                cr="-" if row.citation_recall is None else _fmt(row.citation_recall),
                lat="-" if row.retrieval_latency_ms is None else f"{row.retrieval_latency_ms:.1f}",
                err=row.error or row.judge_error or "",
            )
        )

    lines += _render_interactions(scores)

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _verdict(row: PerExampleScore) -> str:
    """One-line pass/fail summary for a single example -- the "what worked,
    what didn't" signal a bare numbers table doesn't give you. Judgment
    calls here are deliberately conservative: partial citation credit
    still reads as an issue, not a pass, so it doesn't get lost in an
    otherwise-green table."""
    if row.error:
        return f"FAILED -- pipeline error: {row.error}"
    if row.category == "negative":
        if row.negative_false_positive is True:
            return "ISSUE -- fabricated an answer where none should exist (false positive)"
        if row.negative_false_positive is False:
            return "WORKED -- correctly declined to answer (true negative)"
        return "UNSCORED"
    issues: list[str] = []
    if row.hit_at_10 is False:
        issues.append("expected decision never retrieved")
    if row.groundedness is not None and row.groundedness < 1.0:
        issues.append(f"groundedness {row.groundedness:.2f} < 1.0")
    if row.correctness is not None and row.correctness < 1.0:
        issues.append(f"correctness {row.correctness:.2f} < 1.0")
    if row.citation_precision is not None and row.citation_precision < 1.0:
        issues.append(f"over-cited (precision {row.citation_precision:.2f})")
    if row.citation_recall is not None and row.citation_recall < 1.0:
        issues.append(f"under-cited (recall {row.citation_recall:.2f})")
    if row.judge_error:
        issues.append(f"judge call failed: {row.judge_error}")
    if not issues:
        return "WORKED -- retrieved, grounded, correct, cited cleanly"
    return "ISSUE -- " + "; ".join(issues)


def _render_interactions(scores: list[PerExampleScore]) -> list[str]:
    """Full question -> answer -> judge-rationale transcript per example,
    plus a one-line verdict. This is the qualitative complement to the
    numeric tables above: a reviewer can read what the pipeline actually
    said and why the judge scored it that way, not just the score itself."""
    lines = [
        "",
        "## Sample interactions -- what worked, what didn't",
        "",
        "Full question/answer/judge-rationale transcript for every example in this run, "
        "in place of raw numbers alone.",
    ]
    for row in scores:
        lines += [
            "",
            f"### {row.example_id} [{row.category}] -- {_verdict(row)}",
            "",
            f"**Question:** {row.question}",
            "",
            f"**Answer:** {row.answer_text or '(no answer -- see error below)'}",
        ]
        if row.cited_decision_ids:
            lines.append(f"\n**Cited:** {', '.join(row.cited_decision_ids)}")
        if row.judge_rationale:
            lines.append(f"\n**Judge rationale:** {row.judge_rationale}")
        if row.error:
            lines.append(f"\n**Pipeline error:** {row.error}")
        if row.judge_error:
            lines.append(f"\n**Judge error:** {row.judge_error}")
    return lines
