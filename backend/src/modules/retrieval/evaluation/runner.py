"""
run_evaluation() -- scores a RAGPipeline (mock or real, doesn't matter
which, see modules.retrieval.protocol.RAGPipeline) against a GoldenDataset.

This is the module the "no changes needed to runner.py/metrics.py" line
refers to: it imports RAGPipeline as a Protocol, never MockRAGPipeline or
the real RAGPipeline by name, so scripts/run_rag_eval.py swapping which
concrete pipeline it constructs doesn't require touching this file.

Bounded concurrency (default 5 in flight) because the real pipeline makes
two Anthropic calls per example (synthesis + judge) plus two DB round-
trips -- running all 86 examples fully in parallel would either hit rate
limits or just be an unkind way to load-test your own database.
"""
from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

from modules.retrieval.evaluation.golden_dataset import GoldenDataset, GoldenExample
from modules.retrieval.evaluation.llm_judge import judge_answer
from modules.retrieval.evaluation.metrics import (
    EvalReport,
    PerExampleScore,
    citation_precision,
    citation_recall,
    hit_at_k,
    is_negative_false_positive,
    reciprocal_rank,
    recall_at_k,
)
from modules.retrieval.protocol import RAGPipeline
from modules.retrieval.schemas import RetrievalResult

log = logging.getLogger(__name__)

DEFAULT_CONCURRENCY = 5


async def _timed_retrieve(
    pipeline: RAGPipeline, question: str, tenant_id: UUID, top_k: int
) -> tuple[RetrievalResult, float]:
    start = time.monotonic()
    result = await pipeline.retrieve(question, tenant_id, top_k=top_k)
    elapsed_ms = (time.monotonic() - start) * 1000
    return result, elapsed_ms


async def _score_example(
    example: GoldenExample, pipeline: RAGPipeline, top_k: int
) -> PerExampleScore:
    try:
        (retrieval, retrieval_latency_ms), synthesized = await asyncio.gather(
            _timed_retrieve(pipeline, example.question, example.tenant_id, top_k),
            pipeline.answer(example.question, example.tenant_id, top_k=top_k),
        )
    except Exception as exc:  # noqa: BLE001 - one bad example must not kill the run
        log.exception("Pipeline call failed for example %s", example.id)
        return PerExampleScore(
            example_id=example.id,
            category=example.category.value,
            question=example.question,
            recall_at_5=None,
            recall_at_10=None,
            hit_at_5=None,
            hit_at_10=None,
            reciprocal_rank=None,
            negative_false_positive=None,
            groundedness=None,
            correctness=None,
            citation_precision=None,
            citation_recall=None,
            retrieval_latency_ms=None,
            retrieved_decision_ids=[],
            cited_decision_ids=[],
            answer_text="",
            error=f"pipeline call failed: {type(exc).__name__}: {exc}",
        )

    retrieved_ids = retrieval.decision_ids
    cited_ids = synthesized.cited_decision_ids

    groundedness: float | None = None
    correctness: float | None = None
    judge_rationale: str | None = None
    judge_error: str | None = None
    try:
        judged = await judge_answer(
            example.question,
            example.reference_answer,
            synthesized.answer_text,
            [r.decision for r in retrieval.ranked],
            cited_ids,
        )
        groundedness = judged.groundedness
        correctness = judged.correctness
        judge_rationale = judged.rationale
    except Exception as exc:  # noqa: BLE001 - a judge failure degrades this example's score, not the whole run
        log.warning("Judge call failed for example %s: %s", example.id, exc)
        judge_error = f"judge call failed: {type(exc).__name__}: {exc}"

    return PerExampleScore(
        example_id=example.id,
        category=example.category.value,
        question=example.question,
        recall_at_5=recall_at_k(retrieved_ids, example.expected_decision_ids, k=5),
        recall_at_10=recall_at_k(retrieved_ids, example.expected_decision_ids, k=10),
        hit_at_5=hit_at_k(retrieved_ids, example.expected_decision_ids, k=5),
        hit_at_10=hit_at_k(retrieved_ids, example.expected_decision_ids, k=10),
        reciprocal_rank=reciprocal_rank(retrieved_ids, example.expected_decision_ids),
        negative_false_positive=is_negative_false_positive(example.category, cited_ids),
        groundedness=groundedness,
        correctness=correctness,
        citation_precision=citation_precision(cited_ids, example.expected_citation_ids),
        citation_recall=citation_recall(cited_ids, example.expected_citation_ids),
        retrieval_latency_ms=retrieval_latency_ms,
        retrieved_decision_ids=[str(i) for i in retrieved_ids],
        cited_decision_ids=[str(i) for i in cited_ids],
        answer_text=synthesized.answer_text,
        judge_rationale=judge_rationale,
        judge_error=judge_error,
    )


async def run_evaluation(
    dataset: GoldenDataset,
    pipeline: RAGPipeline,
    top_k: int = 10,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> tuple[list[PerExampleScore], EvalReport]:
    """Scores every example in `dataset` against `pipeline`.

    Returns (per_example_scores, aggregate_report). Never raises for an
    individual example's failure -- see PerExampleScore.error -- so a
    single flaky API call degrades that one row's metrics to None rather
    than aborting the whole 86-example run.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded(example: GoldenExample) -> PerExampleScore:
        async with semaphore:
            return await _score_example(example, pipeline, top_k)

    scores = await asyncio.gather(*(_bounded(ex) for ex in dataset.examples))
    scores = list(scores)

    report = EvalReport.from_scores(
        scores, pipeline_name=type(pipeline).__name__, top_k=top_k
    )
    return scores, report
