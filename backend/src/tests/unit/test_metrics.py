"""Unit tests for modules.retrieval.evaluation.metrics -- pure functions."""
from __future__ import annotations

from uuid import uuid4

from modules.retrieval.evaluation.golden_dataset import QuestionCategory
from modules.retrieval.evaluation.metrics import (
    EvalReport,
    PerExampleScore,
    citation_precision,
    citation_recall,
    hit_at_k,
    is_negative_false_positive,
    percentile,
    reciprocal_rank,
    recall_at_k,
)


def test_recall_at_k_full_hit():
    e1, e2 = uuid4(), uuid4()
    assert recall_at_k([e1, e2], [e1, e2], k=5) == 1.0


def test_recall_at_k_partial_hit():
    e1, e2 = uuid4(), uuid4()
    assert recall_at_k([e1], [e1, e2], k=5) == 0.5


def test_recall_at_k_respects_k_boundary():
    e1 = uuid4()
    other = [uuid4() for _ in range(6)]
    retrieved = other[:5] + [e1]  # e1 is rank 6
    assert recall_at_k(retrieved, [e1], k=5) == 0.0
    assert recall_at_k(retrieved, [e1], k=10) == 1.0


def test_recall_at_k_negative_example_is_none():
    assert recall_at_k([uuid4()], [], k=5) is None


def test_reciprocal_rank_first_match():
    e1, e2 = uuid4(), uuid4()
    assert reciprocal_rank([e2, e1], [e1]) == 0.5


def test_reciprocal_rank_no_match_is_zero():
    assert reciprocal_rank([uuid4()], [uuid4()]) == 0.0


def test_reciprocal_rank_negative_example_is_none():
    assert reciprocal_rank([uuid4()], []) is None


def test_is_negative_false_positive_true_when_cited():
    assert is_negative_false_positive(QuestionCategory.NEGATIVE, [uuid4()]) is True


def test_is_negative_false_positive_false_when_not_cited():
    assert is_negative_false_positive(QuestionCategory.NEGATIVE, []) is False


def test_is_negative_false_positive_none_for_non_negative_category():
    assert is_negative_false_positive(QuestionCategory.SINGLE_HOP, [uuid4()]) is None


def _score(**overrides) -> PerExampleScore:
    base = dict(
        example_id="ge-1",
        category="single_hop",
        question="q",
        recall_at_5=1.0,
        recall_at_10=1.0,
        hit_at_5=True,
        hit_at_10=True,
        reciprocal_rank=1.0,
        negative_false_positive=None,
        groundedness=0.8,
        correctness=0.75,
        citation_precision=1.0,
        citation_recall=1.0,
        retrieval_latency_ms=42.0,
        retrieved_decision_ids=[],
        cited_decision_ids=[],
        answer_text="a",
    )
    base.update(overrides)
    return PerExampleScore(**base)


def test_eval_report_aggregates_means():
    scores = [
        _score(example_id="a", recall_at_5=1.0, recall_at_10=1.0, reciprocal_rank=1.0),
        _score(example_id="b", recall_at_5=0.0, recall_at_10=0.0, reciprocal_rank=0.0),
    ]
    report = EvalReport.from_scores(scores, pipeline_name="TestPipeline", top_k=10)
    assert report.recall_at_5 == 0.5
    assert report.recall_at_10 == 0.5
    assert report.mrr == 0.5
    assert report.n_examples == 2
    assert report.n_errors == 0


def test_eval_report_excludes_negative_examples_from_recall_and_mrr():
    scores = [
        _score(example_id="pos", recall_at_5=1.0, recall_at_10=1.0, reciprocal_rank=1.0),
        _score(
            example_id="neg",
            category="negative",
            recall_at_5=None,
            recall_at_10=None,
            reciprocal_rank=None,
            negative_false_positive=True,
        ),
    ]
    report = EvalReport.from_scores(scores, pipeline_name="TestPipeline", top_k=10)
    assert report.recall_at_5 == 1.0  # only the positive example counted
    assert report.negative_hit_rate == 1.0  # the one negative example was a false positive


def test_eval_report_excludes_errored_examples():
    scores = [
        _score(example_id="ok"),
        _score(example_id="broken", error="boom", recall_at_5=None, recall_at_10=None, reciprocal_rank=None, groundedness=None, correctness=None),
    ]
    report = EvalReport.from_scores(scores, pipeline_name="TestPipeline", top_k=10)
    assert report.n_errors == 1
    assert report.recall_at_5 == 1.0  # errored example excluded, not counted as 0


def test_citation_precision_all_cited_correct():
    e1, e2 = uuid4(), uuid4()
    assert citation_precision([e1], [e1, e2]) == 1.0


def test_citation_precision_partial():
    e1, e2, other = uuid4(), uuid4(), uuid4()
    assert citation_precision([e1, other], [e1, e2]) == 0.5


def test_citation_precision_none_cited_is_undefined():
    assert citation_precision([], [uuid4()]) is None


def test_citation_recall_full():
    e1, e2 = uuid4(), uuid4()
    assert citation_recall([e1, e2], [e1, e2]) == 1.0


def test_citation_recall_partial():
    e1, e2 = uuid4(), uuid4()
    assert citation_recall([e1], [e1, e2]) == 0.5


def test_citation_recall_no_expected_citations_is_undefined():
    assert citation_recall([uuid4()], []) is None


def test_percentile_p95_nearest_rank():
    values = [float(i) for i in range(1, 101)]  # 1..100
    assert percentile(values, 95) == 95.0


def test_percentile_empty_is_none():
    assert percentile([], 95) is None


def test_eval_report_includes_citation_and_latency_aggregates():
    scores = [
        _score(example_id="a", citation_precision=1.0, citation_recall=1.0, retrieval_latency_ms=10.0),
        _score(example_id="b", citation_precision=0.0, citation_recall=0.0, retrieval_latency_ms=30.0),
    ]
    report = EvalReport.from_scores(scores, pipeline_name="TestPipeline", top_k=10)
    assert report.citation_precision == 0.5
    assert report.citation_recall == 0.5
    assert report.mean_retrieval_latency_ms == 20.0
    assert report.p95_retrieval_latency_ms in (10.0, 30.0)  # nearest-rank over 2 points

def test_hit_at_k_true_when_any_expected_present():
    e1, e2 = uuid4(), uuid4()
    assert hit_at_k([uuid4(), e1], [e1, e2], k=5) is True


def test_hit_at_k_false_when_none_present_within_k():
    e1 = uuid4()
    others = [uuid4() for _ in range(5)]
    assert hit_at_k(others + [e1], [e1], k=5) is False


def test_hit_at_k_negative_example_is_none():
    assert hit_at_k([uuid4()], [], k=5) is None


def test_hit_at_k_gives_credit_recall_at_k_would_partially_dock():
    # multi_hop-style: 2 expected, only 1 retrieved in top_k -- recall is
    # partial credit (0.5), hit rate is a clean pass (retrieval wasn't a
    # total miss).
    e1, e2 = uuid4(), uuid4()
    from modules.retrieval.evaluation.metrics import recall_at_k

    retrieved = [e1]
    assert recall_at_k(retrieved, [e1, e2], k=5) == 0.5
    assert hit_at_k(retrieved, [e1, e2], k=5) is True


def test_eval_report_hit_rate_aggregation():
    scores = [
        _score(example_id="a", hit_at_5=True, hit_at_10=True),
        _score(example_id="b", hit_at_5=False, hit_at_10=False),
    ]
    report = EvalReport.from_scores(scores, pipeline_name="TestPipeline", top_k=10)
    assert report.hit_rate_at_5 == 0.5
    assert report.hit_rate_at_10 == 0.5
