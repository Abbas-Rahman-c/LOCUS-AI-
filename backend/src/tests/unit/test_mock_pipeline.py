"""Unit tests for modules.retrieval.evaluation.mock_pipeline.MockRAGPipeline."""
from __future__ import annotations

from uuid import uuid4

import pytest

from modules.retrieval.evaluation.mock_pipeline import MockDecisionRecord, MockRAGPipeline

TENANT_A = uuid4()
TENANT_B = uuid4()


def _records() -> list[MockDecisionRecord]:
    return [
        MockDecisionRecord(
            decision_id=uuid4(),
            tenant_id=TENANT_A,
            decision_statement="Move from 5 pricing tiers to a simplified 3-tier structure",
            rationale="Sales says tier confusion stalls deals",
            source_permalink="https://example.internal/pricing",
        ),
        MockDecisionRecord(
            decision_id=uuid4(),
            tenant_id=TENANT_A,
            decision_statement="Adopt a new oncall rotation schedule",
            rationale=None,
            source_permalink="https://example.internal/oncall",
        ),
        MockDecisionRecord(
            decision_id=uuid4(),
            tenant_id=TENANT_B,
            decision_statement="Cross tenant pricing tiers decision that must never leak",
            rationale=None,
            source_permalink="https://example.internal/other-tenant",
        ),
    ]


@pytest.mark.asyncio
async def test_retrieve_ranks_relevant_decision_first():
    pipeline = MockRAGPipeline(decisions=_records())
    result = await pipeline.retrieve("what did we decide about pricing tiers", TENANT_A, top_k=5)
    assert len(result.ranked) >= 1
    assert "pricing" in result.ranked[0].decision.decision_statement.lower()


@pytest.mark.asyncio
async def test_retrieve_never_crosses_tenants():
    pipeline = MockRAGPipeline(decisions=_records())
    result = await pipeline.retrieve("pricing tiers decision", TENANT_A, top_k=10)
    assert all(r.decision.tenant_id == TENANT_A for r in result.ranked)


@pytest.mark.asyncio
async def test_retrieve_unrelated_query_returns_empty():
    pipeline = MockRAGPipeline(decisions=_records())
    result = await pipeline.retrieve("xyzzy quux plugh", TENANT_A, top_k=10)
    assert result.ranked == []


@pytest.mark.asyncio
async def test_answer_cites_top_hit():
    pipeline = MockRAGPipeline(decisions=_records())
    answer = await pipeline.answer("what did we decide about pricing tiers", TENANT_A, top_k=5)
    assert len(answer.citations) == 1
    assert answer.grounded_in  # non-empty


@pytest.mark.asyncio
async def test_answer_with_no_match_says_so():
    pipeline = MockRAGPipeline(decisions=_records())
    answer = await pipeline.answer("xyzzy quux plugh", TENANT_A, top_k=5)
    assert answer.citations == []
    assert "no recorded decision" in answer.answer_text.lower()
