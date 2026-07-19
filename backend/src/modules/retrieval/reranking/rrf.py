"""
Reciprocal Rank Fusion to merge vector + keyword result sets.

RRF scores a candidate by how high it ranks across multiple ranked lists,
without needing the lists' scores to be on comparable scales -- which
matters here because pgvector cosine similarity (bounded [-1, 1], usually
clustered near 1) and Postgres ts_rank (an unbounded, corpus-dependent
float) are not comparable numbers. RRF only looks at *rank position* in
each list:

    score(d) = sum over lists L containing d of  1 / (k + rank_L(d))

A decision that shows up near the top of either leg scores well; a
decision near the top of *both* legs scores best. k=60 is the standard
constant from Cormack et al. 2009 (the paper RRF comes from) -- large
enough that rank 1 vs rank 2 in one list doesn't dominate a candidate that
appears (even lower-ranked) in both lists.
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from modules.retrieval.schemas import RankedDecision, RetrievedDecision
from modules.retrieval.search.hybrid import HybridSearchLegs

DEFAULT_RRF_K = 60

# Fields RetrievedDecision carries per-leg; when the same decision_id shows
# up in more than one input list, the merged record keeps whichever list
# actually populated each of these (never overwrites a set value with None).
_PER_LEG_FIELDS = ("vector_rank", "vector_score", "keyword_rank", "keyword_score")


def _merge_leg_fields(base: RetrievedDecision, other: RetrievedDecision) -> RetrievedDecision:
    updates = {
        field: getattr(other, field)
        for field in _PER_LEG_FIELDS
        if getattr(base, field) is None and getattr(other, field) is not None
    }
    return base.model_copy(update=updates) if updates else base


def reciprocal_rank_fusion(
    result_lists: Sequence[Sequence[RetrievedDecision]],
    *,
    top_k: int = 10,
    k: int = DEFAULT_RRF_K,
) -> list[RankedDecision]:
    """Fuses any number of ranked candidate lists into one ranking.

    Deterministic: ties in rrf_score break on decision_id (string order),
    not insertion/list order, so the same inputs always produce the same
    output regardless of dict iteration order.
    """
    if k <= 0:
        raise ValueError(f"rrf k must be positive, got {k}")
    if top_k <= 0:
        raise ValueError(f"top_k must be positive, got {top_k}")

    scores: dict[UUID, float] = {}
    merged: dict[UUID, RetrievedDecision] = {}

    for candidate_list in result_lists:
        for rank, decision in enumerate(candidate_list, start=1):
            decision_id = decision.decision_id
            scores[decision_id] = scores.get(decision_id, 0.0) + 1.0 / (k + rank)
            merged[decision_id] = (
                _merge_leg_fields(merged[decision_id], decision)
                if decision_id in merged
                else decision
            )

    ordered = sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))[:top_k]

    return [
        RankedDecision(decision=merged[decision_id], rrf_score=score, rank=i + 1)
        for i, (decision_id, score) in enumerate(ordered)
    ]


def fuse_hybrid_legs(
    legs: HybridSearchLegs, *, top_k: int = 10, k: int = DEFAULT_RRF_K
) -> list[RankedDecision]:
    """Convenience wrapper for the two-leg vector+keyword case (what
    modules.retrieval.pipeline actually calls) over the general
    N-list reciprocal_rank_fusion()."""
    return reciprocal_rank_fusion([legs.vector, legs.keyword], top_k=top_k, k=k)
