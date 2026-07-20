"""
Calls Claude Haiku: KEEP | DISCARD | UNCERTAIN

Stage 1 of the AI pipeline. Uses forced tool calling so Claude can only
respond with a single record_triage_result call — never free text — and the
tool's input is validated against TriageResult before it's returned.

anthropic==0.25.x (pinned by pyproject.toml) has no `tools`/`tool_choice`
support on the stable `client.messages.create()` (added in 0.27.0). Tool use
in this SDK line is only reachable via the beta endpoint
`client.beta.tools.messages.create()`, and even that has no typed
`tool_choice` parameter — forcing a specific tool requires passing
`tool_choice` through `extra_body`, which is not visible in the method
signature. Confirmed against the installed package (see
modules.ai.extraction.extractor, which uses the identical pattern).

Reuses modules.retrieval.service.get_anthropic_client() rather than building
a second Anthropic client, matching the convention already established by
modules.answering.provider.
"""
from __future__ import annotations

import os

import anthropic
from pydantic import ValidationError

from modules.ai.prompts.triage_prompt import (
    SYSTEM_PROMPT,
    TRIAGE_TOOL_NAME,
    TRIAGE_TOOL_SCHEMA,
    build_user_message,
)
from modules.ai.triage.schemas import TriageResult
from modules.ingestion.envelope.schemas import EventEnvelope
from modules.retrieval.service import get_anthropic_client

MAX_TOKENS = 128
TEMPERATURE = 0
REQUEST_TIMEOUT_SECONDS = 15.0

APPROVED_TRIAGE_MODELS = {
    "claude-haiku-4-5-20251001",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
}


class TriageClassificationError(Exception):
    """Base class for all classify() failures."""


class TriageToolCallError(TriageClassificationError):
    """Claude did not return the expected forced tool-use block."""


class TriageResultValidationError(TriageClassificationError):
    """The tool_use input did not validate against TriageResult."""


class TriageAPIError(TriageClassificationError):
    """The underlying Anthropic API call failed (HTTP error, timeout, connection)."""


def get_triage_model() -> str:
    """Validate and return the triage model configuration."""
    model = os.environ.get("ANTHROPIC_TRIAGE_MODEL", "claude-haiku-4-5-20251001")
    if model not in APPROVED_TRIAGE_MODELS:
        raise RuntimeError(
            f"ANTHROPIC_TRIAGE_MODEL '{model}' is not in approved list: {sorted(APPROVED_TRIAGE_MODELS)}"
        )
    return model


async def classify(event: EventEnvelope) -> TriageResult:
    """Classify one already-validated EventEnvelope as KEEP / UNCERTAIN / DISCARD.

    Raises TriageAPIError, TriageToolCallError, or TriageResultValidationError
    on failure — callers only need to handle TriageClassificationError. Never
    logs the event's raw_content or the API key.
    """
    client = get_anthropic_client()
    model = get_triage_model()

    try:
        message = await client.beta.tools.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_message(event)}],
            tools=[TRIAGE_TOOL_SCHEMA],
            extra_body={"tool_choice": {"type": "tool", "name": TRIAGE_TOOL_NAME}},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except anthropic.APITimeoutError as exc:
        raise TriageAPIError(f"Anthropic triage call timed out: {exc}") from exc
    except anthropic.APIError as exc:
        raise TriageAPIError(f"Anthropic triage call failed: {exc}") from exc

    tool_use_block = next(
        (block for block in message.content if getattr(block, "type", None) == "tool_use"),
        None,
    )
    if tool_use_block is None:
        raise TriageToolCallError("Claude did not return a tool_use block for the triage call.")
    if tool_use_block.name != TRIAGE_TOOL_NAME:
        raise TriageToolCallError(
            f"Claude called tool '{tool_use_block.name}', expected '{TRIAGE_TOOL_NAME}'."
        )

    try:
        return TriageResult.model_validate(tool_use_block.input)
    except ValidationError as exc:
        raise TriageResultValidationError(
            f"Triage tool input failed TriageResult validation: {exc}"
        ) from exc
