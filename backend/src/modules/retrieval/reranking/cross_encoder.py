"""
Cross-Encoder Reranker — scores each (question, decision) pair jointly
through a small open-source cross-encoder (cross-encoder/ms-marco-MiniLM-
L-6-v2, ~80MB, CPU-friendly, ~120ms for 20 pairs once warm) and returns the
best top_k, replacing RRF/vector-rank ordering with a model that actually
reads the question and the candidate together instead of comparing two
independently-computed embeddings.

Lazily loaded as a module-level singleton on first call (~7s cold start
including a Hugging Face model download the first time it ever runs on a
machine) so importing this module or starting the app never pays that
cost — only the first /search request that reaches reranking does.

Reranking is a quality enhancement, not a security boundary: on any
failure (model load error, predict() exception) this fails OPEN by
returning the input ordering unchanged, never raises out of rerank() into
the request path, and never reorders in a way that could surface a
decision permission filtering already excluded — it only ever reorders
and truncates a list that has already been through
modules.permissions.service.filter_accessible_decisions().
"""
from __future__ import annotations

import logging
import threading

from modules.retrieval.vector.schemas import RetrievalMatch

log = logging.getLogger(__name__)

CROSS_ENCODER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
ENTITY_MATCH_BOOST = 0.5  # additive bonus on the cross-encoder's raw logit score

_model = None
_model_lock = threading.Lock()


def _get_model():
    """Lazily load and cache the cross-encoder model (thread-safe, loads once per process)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # re-check inside the lock (another thread may have loaded it)
                from sentence_transformers import CrossEncoder  # deferred import: torch is heavy

                log.info("Loading cross-encoder model %s (first use in this process)", CROSS_ENCODER_MODEL_NAME)
                _model = CrossEncoder(CROSS_ENCODER_MODEL_NAME)
    return _model


def _candidate_text(match: RetrievalMatch) -> str:
    """Same fields the embedding pipeline indexes on — never raw_content, never fabricated."""
    parts = [match.decision_statement]
    if match.rationale:
        parts.append(match.rationale)
    if match.alternatives_considered:
        parts.append("Alternatives: " + ", ".join(match.alternatives_considered))
    return "\n".join(parts)


def _has_exact_entity_match(text: str, entities: list[str]) -> bool:
    lowered = text.lower()
    return any(entity.lower() in lowered for entity in entities if entity.strip())


def rerank(
    question: str,
    matches: list[RetrievalMatch],
    top_k: int,
    entities: list[str] | None = None,
) -> list[RetrievalMatch]:
    """Rerank matches by cross-encoder relevance to question, return the best top_k.

    entities (from QueryAnalysis) get an additive score boost when they
    appear verbatim in a candidate's text — a simple, explainable heuristic
    on top of the model's own score, not a replacement for it. On any
    reranking failure, logs a warning and returns matches[:top_k] unchanged
    (fail-open on quality, never on security — see module docstring).
    """
    if not matches:
        return []
    if len(matches) <= 1:
        return matches[:top_k]

    try:
        model = _get_model()
        pairs = [(question, _candidate_text(m)) for m in matches]
        raw_scores = model.predict(pairs)
    except Exception:
        log.warning("Cross-encoder reranking failed; falling back to input order.", exc_info=True)
        return matches[:top_k]

    entities = entities or []
    boosted = []
    for match, score in zip(matches, raw_scores):
        final_score = float(score)
        if entities and _has_exact_entity_match(_candidate_text(match), entities):
            final_score += ENTITY_MATCH_BOOST
        boosted.append((final_score, match))

    boosted.sort(key=lambda pair: pair[0], reverse=True)
    reranked = [
        match.model_copy(update={"rerank_score": score})
        for score, match in boosted[:top_k]
    ]
    return reranked
