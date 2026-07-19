"""
Unit tests for modules.retrieval.evaluation.runner.run_evaluation() -- uses
MockRAGPipeline (real, no fakes needed there) plus a patched llm_judge so no
Anthropic call happens in this test.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from modules.retrieval.evaluation.golden_dataset import GoldenDataset, GoldenExample, QuestionCategory
from modules.retrieval.evaluation.mock_pipeline import MockDecisionRecord, MockRAGPipeline
from modules.retrieval.evaluation import runner as runner_module
from modules.retrieval.evaluation.llm_judge import JudgeScore

TENANT = uuid4()
PRICING_DECISION = uuid4()


def _dataset() -> GoldenDataset:
    return GoldenDataset(
        examples=[
            GoldenExample(
                id="ge-1",
                question="what did we decide about pricing tiers",
                tenant_id=TENANT,
                category=QuestionCategory.SINGLE_HOP,
                expected_decision_ids=[PRICING_DECISION],
                expected_citation_ids=[PRICING_DECISION],
                reference_answer="Moved to 3 pricing tiers.",
            ),
            GoldenExample(
                id="ge-2",
                question="have we decided on a company logo redesign",
                tenant_id=TENANT,
                category=QuestionCategory.NEGATIVE,
                expected_decision_ids=[],
                expected_citation_ids=[],
                reference_answer="No decision has been made about a logo redesign.",
            ),
        ]
    )


def _pipeline() -> MockRAGPipeline:
    return MockRAGPipeline(
        decisions=[
            MockDecisionRecord(
                decision_id=PRICING_DECISION,
                tenant_id=TENANT,
                decision_statement="Move from 5 pricing tiers to a simplified 3-tier structure",
                rationale="Reduces sales confusion",
                source_permalink="https://example.internal/pricing",
            )
        ]
    )


@pytest.mark.asyncio
async def test_run_evaluation_scores_single_hop_and_negative_examples():
    fake_judge = AsyncMock(return_value=JudgeScore(groundedness=1.0, correctness=1.0, rationale="ok"))
    with patch.object(runner_module, "judge_answer", fake_judge):
        scores, report = await runner_module.run_evaluation(_dataset(), _pipeline(), top_k=5)

    assert len(scores) == 2
    by_id = {s.example_id: s for s in scores}

    assert by_id["ge-1"].recall_at_5 == 1.0
    assert by_id["ge-1"].hit_at_5 is True
    assert by_id["ge-1"].reciprocal_rank == 1.0
    assert by_id["ge-1"].negative_false_positive is None
    assert by_id["ge-1"].citation_precision == 1.0  # mock cited exactly the expected decision
    assert by_id["ge-1"].citation_recall == 1.0
    assert by_id["ge-1"].retrieval_latency_ms is not None
    assert by_id["ge-1"].retrieval_latency_ms >= 0.0

    assert by_id["ge-2"].recall_at_5 is None  # negative example, undefined
    assert by_id["ge-2"].negative_false_positive is False  # mock correctly found nothing to cite
    assert by_id["ge-2"].citation_precision is None  # nothing cited -- undefined, not zero
    assert by_id["ge-2"].citation_recall is None  # no expected citations -- undefined

    assert report.n_examples == 2
    assert report.n_errors == 0
    assert report.recall_at_5 == 1.0  # averaged only over the single_hop example
    assert report.hit_rate_at_5 == 1.0
    assert report.negative_hit_rate == 0.0
    assert report.groundedness == 1.0
    assert report.correctness == 1.0
    assert report.citation_precision == 1.0
    assert report.citation_recall == 1.0
    assert report.mean_retrieval_latency_ms is not None


@pytest.mark.asyncio
async def test_run_evaluation_records_error_without_aborting_whole_run():
    async def _boom(*args, **kwargs):
        raise RuntimeError("judge is down")

    with patch.object(runner_module, "judge_answer", _boom):
        scores, report = await runner_module.run_evaluation(_dataset(), _pipeline(), top_k=5)

    # judge failures are caught per-example -- pipeline metrics (recall/MRR)
    # still populate even though groundedness/correctness do not, and the
    # example is NOT counted as an error (that's reserved for retrieve()/
    # answer() itself failing).
    assert report.n_examples == 2
    assert report.n_errors == 0
    assert report.recall_at_5 == 1.0
    for s in scores:
        assert s.groundedness is None
        assert s.correctness is None
        assert s.error is None
        assert s.judge_error is not None
