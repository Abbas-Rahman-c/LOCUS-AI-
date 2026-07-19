"""Unit tests for modules.retrieval.reranking.rrf -- pure functions, no I/O."""
from __future__ import annotations

from uuid import uuid4

import pytest

from modules.retrieval.reranking.rrf import fuse_hybrid_legs, reciprocal_rank_fusion
from modules.retrieval.schemas import RetrievedDecision
from modules.retrieval.search.hybrid import HybridSearchLegs

TENANT = uuid4()


def _decision(decision_id, statement="stmt", **kwargs) -> RetrievedDecision:
    return RetrievedDecision(
        decision_id=decision_id,
        tenant_id=TENANT,
        decision_statement=statement,
        status="decided",
        record_type="decision",
        **kwargs,
    )


def test_candidate_in_both_lists_outranks_single_list_candidate():
    a, b, c = uuid4(), uuid4(), uuid4()
    vector = [_decision(a, vector_rank=1), _decision(b, vector_rank=2)]
    keyword = [_decision(a, keyword_rank=1), _decision(c, keyword_rank=2)]

    fused = reciprocal_rank_fusion([vector, keyword], top_k=10)

    assert fused[0].decision.decision_id == a
    assert fused[0].rank == 1
    ids = [f.decision.decision_id for f in fused]
    assert set(ids) == {a, b, c}


def test_rrf_score_matches_formula():
    a = uuid4()
    vector = [_decision(a, vector_rank=1)]
    fused = reciprocal_rank_fusion([vector], top_k=10, k=60)
    assert fused[0].rrf_score == pytest.approx(1.0 / 61)


def test_merged_record_keeps_both_legs_fields():
    a = uuid4()
    vector = [_decision(a, vector_rank=1, vector_score=0.9)]
    keyword = [_decision(a, keyword_rank=3, keyword_score=0.4)]
    fused = reciprocal_rank_fusion([vector, keyword], top_k=10)
    merged = fused[0].decision
    assert merged.vector_rank == 1
    assert merged.vector_score == 0.9
    assert merged.keyword_rank == 3
    assert merged.keyword_score == 0.4


def test_top_k_truncates():
    ids = [uuid4() for _ in range(5)]
    vector = [_decision(i, vector_rank=rank + 1) for rank, i in enumerate(ids)]
    fused = reciprocal_rank_fusion([vector], top_k=2)
    assert len(fused) == 2
    assert [f.rank for f in fused] == [1, 2]


def test_deterministic_tie_break_by_decision_id():
    a, b = sorted([uuid4(), uuid4()], key=str)
    # both appear only in one list at the same rank position across two
    # separate single-item lists -> identical rrf_score, tie broken by id.
    fused = reciprocal_rank_fusion([[_decision(a, vector_rank=1)], [_decision(b, vector_rank=1)]], top_k=10)
    assert [f.decision.decision_id for f in fused] == [a, b]


def test_empty_lists_yield_empty_result():
    assert reciprocal_rank_fusion([[], []], top_k=10) == []


def test_invalid_top_k_or_k_raises():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[]], top_k=0)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[]], top_k=5, k=0)


def test_fuse_hybrid_legs_wraps_two_lists():
    a = uuid4()
    legs = HybridSearchLegs(vector=[_decision(a, vector_rank=1)], keyword=[])
    fused = fuse_hybrid_legs(legs, top_k=5)
    assert len(fused) == 1
    assert fused[0].decision.decision_id == a
