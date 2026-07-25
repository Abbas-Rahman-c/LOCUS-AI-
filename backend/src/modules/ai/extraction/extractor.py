"""
Calls Claude Haiku: extracts one ExtractionResult from a KEEP/UNCERTAIN event.

Stage 2 of the AI pipeline. Reuses the same Anthropic client and the same
beta Tool Use interface as the triage stage — see
modules.ai.triage.classifier for the anthropic==0.25.x SDK compatibility
notes (no tools/tool_choice on the stable messages.create(); tool_choice
must go through extra_body on client.beta.tools.messages.create()). Claude
can only respond with a single record_extraction_result call, whose input is
validated against ExtractionResult before it's returned.
"""
from __future__ import annotations

import os

import anthropic
from pydantic import ValidationError

from modules.ai.extraction.schemas import ExtractionResult
from modules.ai.prompts.extraction_prompt import (
    EXTRACTION_TOOL_NAME,
    EXTRACTION_TOOL_SCHEMA,
    SYSTEM_PROMPT,
    build_user_message,
)
from modules.ingestion.envelope.schemas import EventEnvelope
from modules.retrieval.service import get_anthropic_client

MAX_TOKENS = 512
TEMPERATURE = 0
REQUEST_TIMEOUT_SECONDS = 30.0

APPROVED_EXTRACTION_MODELS = {
    "claude-haiku-4-5-20251001",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
}


class ExtractionError(Exception):
    """Base class for all extract() failures."""


class ExtractionToolCallError(ExtractionError):
    """Claude did not return the expected forced tool-use block."""


class ExtractionResultValidationError(ExtractionError):
    """The tool_use input did not validate against ExtractionResult."""


class ExtractionAPIError(ExtractionError):
    """The underlying Anthropic API call failed (HTTP error, timeout, connection)."""


def get_extraction_model() -> str:
    """Validate and return the extraction model configuration."""
    model = os.environ.get("ANTHROPIC_EXTRACT_MODEL", "claude-haiku-4-5-20251001")
    if model not in APPROVED_EXTRACTION_MODELS:
        raise RuntimeError(
            f"ANTHROPIC_EXTRACT_MODEL '{model}' is not in approved list: {sorted(APPROVED_EXTRACTION_MODELS)}"
        )
    return model


async def extract(event: EventEnvelope) -> ExtractionResult:
    """Extract one ExtractionResult from an already-validated EventEnvelope.

    Raises ExtractionAPIError, ExtractionToolCallError, or
    ExtractionResultValidationError on failure — callers only need to handle
    ExtractionError. Never logs the event's raw_content or the API key.
    """
    client = get_anthropic_client()
    model = get_extraction_model()

    try:
        message = await client.beta.tools.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_message(event)}],
            tools=[EXTRACTION_TOOL_SCHEMA],
            extra_body={"tool_choice": {"type": "tool", "name": EXTRACTION_TOOL_NAME}},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except anthropic.APITimeoutError as exc:
        raise ExtractionAPIError(f"Anthropic extraction call timed out: {exc}") from exc
    except anthropic.APIError as exc:
        raise ExtractionAPIError(f"Anthropic extraction call failed: {exc}") from exc

    tool_use_block = next(
        (block for block in message.content if getattr(block, "type", None) == "tool_use"),
        None,
    )
    if tool_use_block is None:
        raise ExtractionToolCallError("Claude did not return a tool_use block for the extraction call.")
    if tool_use_block.name != EXTRACTION_TOOL_NAME:
        raise ExtractionToolCallError(
            f"Claude called tool '{tool_use_block.name}', expected '{EXTRACTION_TOOL_NAME}'."
        )

    try:
        return ExtractionResult.model_validate(tool_use_block.input)
    except ValidationError as exc:
        raise ExtractionResultValidationError(
            f"Extraction tool input failed ExtractionResult validation: {exc}"
        ) from exc
