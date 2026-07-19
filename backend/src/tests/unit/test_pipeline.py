"""
End-to-end wiring test for modules.retrieval.pipeline.RAGPipeline -- fakes
the DB pool and Anthropic client, asserts hybrid search -> RRF -> synthesis
-> citation resolution all connect correctly with no real I/O.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from modules.retrieval.pipeline import RAGPipeline
from modules.retrieval.search import hybrid
from tests.fixtures.fakes import FakeAnthropicClient, FakeConnection, FakePool, make_tool_use_message

TENANT = uuid4()
DECISION_ID = uuid4()


def _fake_pool() -> FakePool:
    conn = FakeConnection(
        fetch_by_marker={
            "decision_embeddings": [
                {
                    "id": DECISION_ID,
                    "tenant_id": TENANT,
                    "decision_statement": "Move from 5 pricing tiers to 3 tiers",
                    "rationale": "Reduces sales confusion",
                    "status": "decided",
                    "record_type": "decision",
                    "cosine_similarity": 0.92,
                }
            ],
            "plainto_tsquery": [],
            "decision_sources": [{"decision_id": DECISION_ID, "permalink": "https://example.internal/pricing"}],
        }
    )
    return FakePool(conn)


@pytest.mark.asyncio
async def test_retrieve_returns_fused_ranking():
    pool = _fake_pool()
    pipeline = RAGPipeline(pool=pool)
    with patch.object(hybrid, "embed_query", AsyncMock(return_value=[0.1, 0.2])):
        result = await pipeline.retrieve("what did we decide about pricing tiers", TENANT, top_k=5)
    assert len(result.ranked) == 1
    assert result.ranked[0].decision.decision_id == DECISION_ID


@pytest.mark.asyncio
async def test_answer_produces_grounded_cited_answer_with_resolved_permalink():
    pool = _fake_pool()
    anthropic_client = FakeAnthropicClient(
        make_tool_use_message(
            "submit_answer",
            {
                "answer": "Moved to a simplified 3-tier structure. [D1]",
                "cited_labels": ["D1"],
                "no_relevant_decisions": False,
            },
        )
    )
    pipeline = RAGPipeline(pool=pool, anthropic_client=anthropic_client, anthropic_model="claude-test")

    with patch.object(hybrid, "embed_query", AsyncMock(return_value=[0.1, 0.2])):
        answer = await pipeline.answer("what did we decide about pricing tiers", TENANT, top_k=5)

    assert answer.cited_decision_ids == [DECISION_ID]
    assert answer.citations[0].permalink == "https://example.internal/pricing"
    assert answer.grounded_in == [DECISION_ID]


@pytest.mark.asyncio
async def test_answer_with_no_candidates_never_calls_anthropic():
    conn = FakeConnection(fetch_by_marker={"decision_embeddings": [], "plainto_tsquery": []})
    pool = FakePool(conn)
    anthropic_client = FakeAnthropicClient(make_tool_use_message("submit_answer", {}))
    pipeline = RAGPipeline(pool=pool, anthropic_client=anthropic_client)

    with patch.object(hybrid, "embed_query", AsyncMock(return_value=[0.1])):
        answer = await pipeline.answer("totally unrelated question", TENANT, top_k=5)

    assert answer.citations == []
    assert anthropic_client.messages.calls == []
