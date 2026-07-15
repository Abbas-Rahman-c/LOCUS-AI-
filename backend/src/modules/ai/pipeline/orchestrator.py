"""
AI pipeline orchestrator  runs the full triage ? extraction ? embed ? confidence ? store chain.

pgmq NOTE: This module does NOT create its own queue connection.
If it needs to re-enqueue (e.g. for retry), it imports from:
  queue.pgmq.producer ? enqueue_event() / enqueue_embedding_job()
"""
from __future__ import annotations
import logging

log = logging.getLogger(__name__)


async def run_pipeline(chunk: dict) -> None:
    """Run the two-stage AI pipeline on a single text chunk.
    
    Stage 1: Haiku triage   (modules/ai/triage/classifier.py)
    Stage 2: Sonnet extract (modules/ai/extraction/extractor.py)
    Post:     Embed summary  (modules/ai/embeddings/provider.py)
              Score confidence (modules/ai/confidence/scorer.py)
              Persist capture  (modules/captures/service.py)
    """
    from modules.ai.triage.classifier import classify
    from modules.ai.extraction.extractor import extract
    from modules.ai.embeddings.provider import embed
    from modules.ai.confidence.scorer import score
    from modules.captures.service import save_capture

    triage = await classify(chunk)
    if triage.decision == "DISCARD":
        log.debug("Triage DISCARD  chunk skipped")
        return

    extraction = await extract(chunk)
    if not extraction:
        log.warning("Sonnet extraction returned no items  chunk skipped")
        return

    for item in extraction.items:
        embedding = await embed(item.summary)
        confidence = await score(item.confidence)
        await save_capture(item, embedding, confidence, source_chunk=chunk)
