"""
Claude Answer Service — generate_answer() is the single entry point that
turns one question + one Context Builder context string into a grounded
AnswerResult, via modules.answering.provider (reusing the existing
Anthropic client/model from modules.retrieval.service).

Single-turn only: no conversation history, no streaming, no RAG
re-retrieval, no memory. Structured tool output (see prompt_builder) means
citations are Claude's own explicit list, not regex-parsed from prose.

Refusal enforcement: whenever Claude reports sufficient_evidence=False,
this service - not Claude - sets the final answer to REFUSAL_TEXT verbatim
and forces citations to []. This is deliberate defense in depth: even if
Claude's free-text `answer` field says something slightly different, or
its `citations` list is non-empty by mistake, the caller-visible result on
a refusal is always exactly REFUSAL_TEXT with zero citations - closing the
false-positive-citation-on-refusal bug found during evaluation (Claude's
own refusal explanation could previously get regex-matched for a stray
"Decision N" mention and misreported as a real citation).
"""
from __future__ import annotations

import logging
import time

from modules.answering.prompt_builder import REFUSAL_TEXT, build_system_prompt, build_user_message
from modules.answering.provider import generate_completion
from modules.answering.schemas import AnswerResult
from modules.query_understanding.schemas import QueryAnalysis

log = logging.getLogger(__name__)


async def generate_answer(
    question: str,
    context: str,
    query_analysis: QueryAnalysis | None = None,
) -> AnswerResult:
    """Generate one grounded answer for question, using only context.

    query_analysis is optional and additive: when supplied, its
    is_multi_document flag adjusts the system prompt to ask for a
    structured multi-decision summary, and its intent/question_type are
    surfaced to Claude for context. Omitting it (None) reproduces the
    single-document prompt behavior.

    Raises whatever generate_completion() raises: AnswerAPIError,
    AnswerToolCallError, or AnswerResponseValidationError.
    """
    start = time.perf_counter()

    system_prompt = build_system_prompt(query_analysis)
    user_message = build_user_message(question, context, query_analysis)
    tool_output, model = await generate_completion(system_prompt, user_message)

    latency_ms = (time.perf_counter() - start) * 1000

    if tool_output.sufficient_evidence:
        answer, citations = tool_output.answer, sorted(set(tool_output.citations))
    else:
        answer, citations = REFUSAL_TEXT, []

    log.info(
        "Claude answer: model=%s sufficient_evidence=%s citations=%s confidence=%.3f latency_ms=%.3f",
        model, tool_output.sufficient_evidence, citations, tool_output.confidence, latency_ms,
    )

    return AnswerResult(
        answer=answer,
        reasoning=tool_output.reasoning,
        citations=citations,
        confidence=tool_output.confidence,
        sufficient_evidence=tool_output.sufficient_evidence,
        model=model,
        latency_ms=latency_ms,
    )
