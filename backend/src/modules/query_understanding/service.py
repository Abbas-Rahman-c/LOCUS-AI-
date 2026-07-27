"""
Query Understanding Service — analyze_query() is the single entry point
that turns a raw question into a QueryAnalysis, via one forced Claude tool
call. Reuses modules.retrieval.service.get_anthropic_client() /
get_synthesis_model() rather than building a new client or a new
model/env-var pair — this call is architecturally identical to answer
synthesis (structured Haiku extraction), just a different tool schema.

anthropic==0.25.x has no `tools`/`tool_choice` on the stable
client.messages.create() — tool use requires the beta endpoint
client.beta.tools.messages.create(), with tool_choice forced via
extra_body (identical constraint documented in
modules.ai.triage.classifier).
"""
from __future__ import annotations

import logging

import anthropic
from pydantic import ValidationError

from modules.query_understanding.prompt import (
    QUERY_ANALYSIS_TOOL_NAME,
    QUERY_ANALYSIS_TOOL_SCHEMA,
    SYSTEM_PROMPT,
    build_user_message,
)
from modules.query_understanding.schemas import QueryAnalysis
from modules.retrieval.service import get_anthropic_client, get_synthesis_model

log = logging.getLogger(__name__)

MAX_TOKENS = 512
TEMPERATURE = 0
REQUEST_TIMEOUT_SECONDS = 15.0


class QueryAnalysisError(Exception):
    """Base class for all analyze_query() failures."""


class QueryAnalysisAPIError(QueryAnalysisError):
    """The underlying Anthropic API call failed (HTTP error, timeout, connection)."""


class QueryAnalysisToolCallError(QueryAnalysisError):
    """Claude did not return the expected forced tool-use block."""


class QueryAnalysisValidationError(QueryAnalysisError):
    """The tool_use input did not validate against QueryAnalysis."""


async def analyze_query(question: str) -> QueryAnalysis:
    """Analyze one question before retrieval. Raises QueryAnalysisError subclasses on failure.

    Callers that want /search to degrade gracefully rather than fail
    outright on an analysis error should catch QueryAnalysisError and fall
    back to modules.query_understanding.schemas.NULL_QUERY_ANALYSIS — see
    modules.search.service for that fallback.
    """
    client = get_anthropic_client()
    model = get_synthesis_model()

    try:
        message = await client.beta.tools.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_message(question)}],
            tools=[QUERY_ANALYSIS_TOOL_SCHEMA],
            extra_body={"tool_choice": {"type": "tool", "name": QUERY_ANALYSIS_TOOL_NAME}},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except anthropic.APITimeoutError as exc:
        raise QueryAnalysisAPIError(f"Query analysis call timed out: {exc}") from exc
    except anthropic.APIError as exc:
        raise QueryAnalysisAPIError(f"Query analysis call failed: {exc}") from exc

    tool_use_block = next(
        (block for block in message.content if getattr(block, "type", None) == "tool_use"),
        None,
    )
    if tool_use_block is None:
        raise QueryAnalysisToolCallError("Claude did not return a tool_use block for query analysis.")
    if tool_use_block.name != QUERY_ANALYSIS_TOOL_NAME:
        raise QueryAnalysisToolCallError(
            f"Claude called tool '{tool_use_block.name}', expected '{QUERY_ANALYSIS_TOOL_NAME}'."
        )

    try:
        analysis = QueryAnalysis.model_validate(tool_use_block.input)
    except ValidationError as exc:
        raise QueryAnalysisValidationError(f"Query analysis tool input failed validation: {exc}") from exc

    log.info(
        "Query analysis: question_type=%s is_multi_document=%s entities=%s keywords=%s department_guess=%r",
        analysis.question_type, analysis.is_multi_document, analysis.entities,
        analysis.keywords, analysis.department_guess,
    )
    return analysis
