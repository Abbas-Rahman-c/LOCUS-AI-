"""
Claude Answer Service — generate_answer() is the single entry point that
turns one question + one Context Builder context string into a grounded
AnswerResult, via modules.answering.provider (reusing the existing
Anthropic client/model from modules.retrieval.service).

Single-turn only: no conversation history, no streaming, no tool calling,
no RAG re-retrieval, no memory.
"""
from __future__ import annotations

import logging
import re
import time

from modules.answering.prompt_builder import SYSTEM_PROMPT, build_user_message
from modules.answering.provider import generate_completion
from modules.answering.schemas import AnswerResult

log = logging.getLogger(__name__)

_CITATION_PATTERN = re.compile(r"[Dd]ecision\s+(\d+)")


def _extract_citations(answer: str) -> list[int]:
    """Decision numbers Claude's answer text actually cites, deduped and sorted.

    A pure text-parsing step over Claude's own output - never adds a
    citation Claude didn't write. Whether a cited number actually
    corresponds to an authorized decision is validated separately, by the
    caller, once the authorized-decision list is available (see
    modules.search.service._build_citations).
    """
    numbers = {int(match) for match in _CITATION_PATTERN.findall(answer)}
    return sorted(numbers)


async def generate_answer(question: str, context: str) -> AnswerResult:
    """Generate one grounded answer for question, using only context.

    Raises whatever generate_completion() raises: AnswerAPIError or
    AnswerResponseValidationError.
    """
    start = time.perf_counter()

    user_message = build_user_message(question, context)
    answer_text, model = await generate_completion(SYSTEM_PROMPT, user_message)

    latency_ms = (time.perf_counter() - start) * 1000
    citations = _extract_citations(answer_text)

    log.info(
        "Claude answer: model=%s citations=%s latency_ms=%.3f",
        model,
        citations,
        latency_ms,
    )

    return AnswerResult(answer=answer_text, citations=citations, model=model, latency_ms=latency_ms)
