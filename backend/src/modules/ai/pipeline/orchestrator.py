"""
AI pipeline orchestrator  runs the full triage ? extraction ? embed ? confidence ? store chain.

pgmq NOTE: This module does NOT create its own queue connection.
If it needs to re-enqueue (e.g. for retry), it imports from:
  queues.pgmq.producer → enqueue_event() / enqueue_embedding_job()
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


# ═══════════════════════════════════════════════════════════════════════
# Standalone AI pipeline (triage -> extraction only)
#
# process_ai_event() is independent of run_pipeline() above: it takes an
# EventEnvelope (not a chunk dict), never embeds, scores, or persists, and
# returns its result instead of side-effecting. It does not add tenant_id,
# permission_scope, database ids, timestamps, model name, or prompt version
# — callers that need those own that responsibility (see
# modules.ai.pipeline.service.process_and_persist_event()).
# ═══════════════════════════════════════════════════════════════════════

from modules.ai.extraction.extractor import ExtractionError, extract
from modules.ai.pipeline.schemas import AIProcessingResult
from modules.ai.triage.classifier import TriageClassificationError, classify
from modules.ai.triage.schemas import TriageDecision
from modules.ingestion.envelope.schemas import EventEnvelope


class AIPipelineError(Exception):
    """Base class for all process_ai_event() failures."""


class ClassificationStageError(AIPipelineError):
    """The triage stage (classify()) failed."""


class ExtractionStageError(AIPipelineError):
    """The extraction stage (extract()) failed."""


async def process_ai_event(event: EventEnvelope) -> AIProcessingResult:
    """Run triage, then extraction unless triage discarded the event.

    KEEP and UNCERTAIN are both extracted — UNCERTAIN is never silently
    treated as KEEP or as DISCARD, it just follows the same "attempt
    extraction" path KEEP does. Only DISCARD skips extraction.
    """
    try:
        triage = await classify(event)
    except TriageClassificationError as exc:
        raise ClassificationStageError(f"Triage classification failed: {exc}") from exc

    if triage.decision == TriageDecision.DISCARD:
        log.debug("Triage DISCARD - extraction skipped")
        return AIProcessingResult(triage=triage, extraction=None)

    try:
        extraction = await extract(event)
    except ExtractionError as exc:
        raise ExtractionStageError(f"Extraction failed: {exc}") from exc

    return AIProcessingResult(triage=triage, extraction=extraction)
