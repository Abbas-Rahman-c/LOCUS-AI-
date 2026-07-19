"""
Retrieval/RAG evaluation metrics -- pure functions over ids and judge
scores, no I/O. modules.retrieval.evaluation.runner calls these once per
golden example and aggregates into an EvalReport.

Recall@K and MRR are only meaningful for examples with a non-empty
expected_decision_ids -- QuestionCategory.NEGATIVE examples are excluded
from both (recall_at_k/reciprocal_rank return None for them) and instead
feed negative_hit_rate, which measures the opposite failure mode: did the
pipeline confidently cite a decision for a question that has none.

Citation quality (citation_precision/citation_recall) is a distinct signal
from recall_at_k: recall_at_k asks whether the right decision was
*retrieved* anywhere in the candidate pool; citation quality asks whether
the *synthesized answer* actually cited the right decision(s), scored
against GoldenExample.expected_citation_ids -- the subset of
expected_decision_ids a correct answer MUST cite. A pipeline can retrieve
the right decision and still cite the wrong one (or nothing).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from modules.retrieval.evaluation.golden_dataset import QuestionCategory


def recall_at_k(retrieved_ids: list[UUID], expected_ids: list[UUID], k: int) -> float | None:
    """Fraction of expected_ids present in the first k retrieved_ids.
    Returns None (undefined, not zero) if expected_ids is empty."""
    if not expected_ids:
        return None
    top_k = set(retrieved_ids[:k])
    hits = sum(1 for e in expected_ids if e in top_k)
    return hits / len(expected_ids)


def reciprocal_rank(retrieved_ids: list[UUID], expected_ids: list[UUID]) -> float | None:
    """1 / (rank of the first expected id found in retrieved_ids), 0.0 if
    none are found anywhere in retrieved_ids, None if expected_ids is empty."""
    if not expected_ids:
        return None
    expected_set = set(expected_ids)
    for i, retrieved_id in enumerate(retrieved_ids, start=1):
        if retrieved_id in expected_set:
            return 1.0 / i
    return 0.0


def citation_precision(cited_ids: list[UUID], expected_citation_ids: list[UUID]) -> float | None:
    """Fraction of cited_ids that were actually expected. None (undefined)
    if nothing was cited -- an uncited answer has no precision to score,
    that failure mode is citation_recall's job (and negative_hit_rate's,
    for the negative-category case)."""
    if not cited_ids:
        return None
    expected_set = set(expected_citation_ids)
    hits = sum(1 for c in cited_ids if c in expected_set)
    return hits / len(cited_ids)


def citation_recall(cited_ids: list[UUID], expected_citation_ids: list[UUID]) -> float | None:
    """Fraction of expected_citation_ids that were actually cited. None
    (undefined, not zero) if expected_citation_ids is empty -- matches
    recall_at_k/reciprocal_rank's convention for the negative-category case."""
    if not expected_citation_ids:
        return None
    cited_set = set(cited_ids)
    hits = sum(1 for e in expected_citation_ids if e in cited_set)
    return hits / len(expected_citation_ids)


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile (p in [0, 100]), no interpolation -- good
    enough for eyeballing p95 retrieval latency without pulling in numpy."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, min(len(ordered), math.ceil(p / 100 * len(ordered))))
    return ordered[rank - 1]


def hit_at_k(retrieved_ids: list[UUID], expected_ids: list[UUID], k: int) -> bool | None:
    """Whether at least one expected id appears in the first k retrieved_ids
    -- the standard Hit Rate@K / Success@K retrieval-accuracy metric. This
    is "overall retrieval accuracy": a single pass/fail signal, distinct
    from recall_at_k's partial credit -- a multi_hop example with 2
    expected decisions and only 1 retrieved scores recall_at_k=0.5 but
    hit_at_k=True (retrieval wasn't a total miss). None if expected_ids is
    empty (negative examples -- same convention as recall_at_k)."""
    if not expected_ids:
        return None
    top_k = set(retrieved_ids[:k])
    return any(e in top_k for e in expected_ids)


def is_negative_false_positive(category: QuestionCategory, cited_decision_ids: list[UUID]) -> bool | None:
    """True if this is a negative example AND the pipeline cited something
    anyway (a false positive). None if this isn't a negative example --
    negative_hit_rate averages only over the True/False values."""
    if category != QuestionCategory.NEGATIVE:
        return None
    return len(cited_decision_ids) > 0


@dataclass
class PerExampleScore:
    """One golden example's full scoring detail -- written to eval_report.json
    verbatim so a prompt-tuning diff can see exactly which examples moved."""

    example_id: str
    category: str
    question: str
    recall_at_5: float | None
    recall_at_10: float | None
    hit_at_5: bool | None
    hit_at_10: bool | None
    reciprocal_rank: float | None
    negative_false_positive: bool | None
    groundedness: float | None
    correctness: float | None
    citation_precision: float | None
    citation_recall: float | None
    retrieval_latency_ms: float | None
    retrieved_decision_ids: list[str]
    cited_decision_ids: list[str]
    answer_text: str
    judge_rationale: str | None = None
    error: str | None = None  # set only when retrieve()/answer() itself failed -- voids the whole row
    judge_error: str | None = None  # set only when the LLM judge call failed -- recall/MRR stay valid


def _mean(values: list[float]) -> float | None:
    """None (not 0.0) when there's nothing to average -- e.g. groundedness
    with zero successfully-judged examples must read as "not measured",
    never as "scored zero"."""
    return sum(values) / len(values) if values else None


@dataclass
class EvalReport:
    """Aggregate metrics across the whole golden set. Field names match
    what scripts/run_rag_eval.py already prints (report.recall_at_5, etc.),
    so building this file didn't require touching that script's output
    format, only where it imports from."""

    pipeline_name: str
    top_k: int
    n_examples: int
    recall_at_5: float | None
    recall_at_10: float | None
    hit_rate_at_5: float | None
    hit_rate_at_10: float | None
    mrr: float | None
    negative_hit_rate: float | None
    groundedness: float | None
    correctness: float | None
    citation_precision: float | None
    citation_recall: float | None
    mean_retrieval_latency_ms: float | None
    p95_retrieval_latency_ms: float | None
    category_coverage: dict[str, int]
    n_errors: int
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_scores(
        cls, scores: list[PerExampleScore], *, pipeline_name: str, top_k: int
    ) -> EvalReport:
        # Pipeline-level failures (retrieve()/answer() itself raised) void an
        # example entirely. A judge-only failure (judge_error set, error not)
        # still contributes valid recall/MRR/negative-hit-rate signal -- it
        # only withholds groundedness/correctness, which is why those two
        # are aggregated over `scores` directly rather than `pipeline_ok`.
        pipeline_ok = [s for s in scores if s.error is None]

        recall_5_vals = [s.recall_at_5 for s in pipeline_ok if s.recall_at_5 is not None]
        recall_10_vals = [s.recall_at_10 for s in pipeline_ok if s.recall_at_10 is not None]
        hit_5_vals = [s.hit_at_5 for s in pipeline_ok if s.hit_at_5 is not None]
        hit_10_vals = [s.hit_at_10 for s in pipeline_ok if s.hit_at_10 is not None]
        rr_vals = [s.reciprocal_rank for s in pipeline_ok if s.reciprocal_rank is not None]
        neg_vals = [s.negative_false_positive for s in pipeline_ok if s.negative_false_positive is not None]
        groundedness_vals = [s.groundedness for s in scores if s.groundedness is not None]
        correctness_vals = [s.correctness for s in scores if s.correctness is not None]
        citation_precision_vals = [s.citation_precision for s in pipeline_ok if s.citation_precision is not None]
        citation_recall_vals = [s.citation_recall for s in pipeline_ok if s.citation_recall is not None]
        latency_vals = [s.retrieval_latency_ms for s in pipeline_ok if s.retrieval_latency_ms is not None]

        coverage: dict[str, int] = {}
        for s in scores:
            coverage[s.category] = coverage.get(s.category, 0) + 1

        return cls(
            pipeline_name=pipeline_name,
            top_k=top_k,
            n_examples=len(scores),
            recall_at_5=_mean(recall_5_vals),
            recall_at_10=_mean(recall_10_vals),
            hit_rate_at_5=_mean([1.0 if v else 0.0 for v in hit_5_vals]) if hit_5_vals else None,
            hit_rate_at_10=_mean([1.0 if v else 0.0 for v in hit_10_vals]) if hit_10_vals else None,
            mrr=_mean(rr_vals),
            negative_hit_rate=_mean([1.0 if v else 0.0 for v in neg_vals]) if neg_vals else None,
            groundedness=_mean(groundedness_vals),
            correctness=_mean(correctness_vals),
            citation_precision=_mean(citation_precision_vals),
            citation_recall=_mean(citation_recall_vals),
            mean_retrieval_latency_ms=_mean(latency_vals),
            p95_retrieval_latency_ms=percentile(latency_vals, 95),
            category_coverage=coverage,
            n_errors=len(scores) - len(pipeline_ok),
        )
