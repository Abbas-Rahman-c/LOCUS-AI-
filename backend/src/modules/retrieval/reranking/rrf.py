"""
Reciprocal Rank Fusion (RRF) — merges the independently-ranked vector and
keyword result lists into one fused ranking, by RANK POSITION only, never
by comparing the two methods' raw scores (cosine similarity vs. FTS
ts_rank use incomparable scales, so combining the numbers directly would
be meaningless).

RRF score for one decision = sum, over every input list it appears in, of
1 / (k + rank), where rank is that list's 1-indexed position. A decision
retrieved by only one method still gets a score from that one list; a
decision retrieved by both gets the sum of both contributions - this is
exactly how RRF rewards results the two methods agree on, without either
method's score ever needing to be normalized against the other.
"""
from __future__ import annotations

from uuid import UUID

from modules.retrieval.vector.schemas import RetrievalMatch

DEFAULT_RRF_K = 60


def fuse_rrf(
    vector_matches: list[RetrievalMatch],
    keyword_matches: list[RetrievalMatch],
    top_k: int,
    k: int = DEFAULT_RRF_K,
) -> list[RetrievalMatch]:
    """Fuse two independently-ranked result lists into one, sorted by
    descending RRF score, deduplicated by decision_id, truncated to top_k.

    Each input list is assumed already sorted best-first (rank 1 = index 0)
    by its own method. Only list position is read - never similarity_score
    - so the two methods' incomparable scales never need reconciling.
    """
    scores: dict[UUID, float] = {}
    by_id: dict[UUID, RetrievalMatch] = {}

    for source_list in (vector_matches, keyword_matches):
        for rank, match in enumerate(source_list, start=1):
            scores[match.decision_id] = scores.get(match.decision_id, 0.0) + 1.0 / (k + rank)
            # First list wins on field values when a decision appears in
            # both - harmless, since both queries read the same
            # public.decisions row and the values are identical either way.
            by_id.setdefault(match.decision_id, match)

    fused = sorted(by_id.values(), key=lambda m: scores[m.decision_id], reverse=True)

    return [
        match.model_copy(update={"rrf_score": scores[match.decision_id]})
        for match in fused[:top_k]
    ]
