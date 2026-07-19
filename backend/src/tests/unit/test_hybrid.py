"""
Unit tests for modules.retrieval.search.hybrid -- no live Postgres. FakePool/
FakeConnection route by SQL substring so both concurrent legs get their own
canned rows regardless of asyncio.gather scheduling order.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from modules.retrieval.search import hybrid
from tests.fixtures.fakes import FakeConnection, FakePool

TENANT = uuid4()
DECISION_A = uuid4()
DECISION_B = uuid4()


def _vector_row(decision_id, score):
    return {
        "id": decision_id,
        "tenant_id": TENANT,
        "decision_statement": "stmt",
        "rationale": "rationale",
        "status": "decided",
        "record_type": "decision",
        "cosine_similarity": score,
    }


def _keyword_row(decision_id, score):
    return {
        "id": decision_id,
        "tenant_id": TENANT,
        "decision_statement": "stmt",
        "rationale": "rationale",
        "status": "decided",
        "record_type": "decision",
        "keyword_rank": score,
    }


@pytest.mark.asyncio
async def test_hybrid_search_runs_both_legs_and_ranks_by_score():
    conn = FakeConnection(
        fetch_by_marker={
            "decision_embeddings": [_vector_row(DECISION_A, 0.9), _vector_row(DECISION_B, 0.5)],
            "plainto_tsquery": [_keyword_row(DECISION_B, 0.8)],
        }
    )
    pool = FakePool(conn)

    with patch.object(hybrid, "embed_query", AsyncMock(return_value=[0.1, 0.2, 0.3])):
        legs = await hybrid.hybrid_search("what did we decide", TENANT, top_k=5, pool=pool)

    assert [r.decision_id for r in legs.vector] == [DECISION_A, DECISION_B]
    assert legs.vector[0].vector_score == 0.9
    assert [r.decision_id for r in legs.keyword] == [DECISION_B]


@pytest.mark.asyncio
async def test_hybrid_search_every_query_carries_tenant_predicate():
    conn = FakeConnection(fetch_by_marker={"decision_embeddings": [], "plainto_tsquery": []})
    pool = FakePool(conn)

    with patch.object(hybrid, "embed_query", AsyncMock(return_value=[0.1])):
        await hybrid.hybrid_search("query text", TENANT, top_k=5, pool=pool)

    fetch_calls = [c for c in conn.calls if c[0] == "fetch"]
    assert len(fetch_calls) == 2
    for _, query, args in fetch_calls:
        assert "tenant_id = $1" in query
        assert args[0] == TENANT

    # tenant GUC is set via execute() before each fetch (set_current_tenant_id)
    execute_calls = [c for c in conn.calls if c[0] == "execute"]
    assert any("app.current_tenant_id" in q for _, q, _ in execute_calls)


@pytest.mark.asyncio
async def test_hybrid_search_rejects_missing_tenant():
    with pytest.raises(ValueError):
        await hybrid.hybrid_search("q", None, top_k=5, pool=FakePool(FakeConnection()))


@pytest.mark.asyncio
async def test_hybrid_search_rejects_blank_query():
    with pytest.raises(ValueError):
        await hybrid.hybrid_search("   ", TENANT, top_k=5, pool=FakePool(FakeConnection()))


@pytest.mark.asyncio
async def test_vector_leg_error_wraps_embedding_failure():
    from modules.ai.embeddings.provider import VoyageEmbeddingError

    conn = FakeConnection()
    pool = FakePool(conn)
    with patch.object(hybrid, "embed_query", AsyncMock(side_effect=VoyageEmbeddingError("boom"))):
        with pytest.raises(hybrid.VectorLegError):
            await hybrid.hybrid_search("q", TENANT, top_k=5, pool=pool)


def test_candidate_pool_size_scales_with_top_k():
    assert hybrid._candidate_pool_size(10) == 40
    assert hybrid._candidate_pool_size(2) == hybrid.MIN_CANDIDATE_POOL
