"""
Claude Answer Provider — single-turn structured completion via forced tool
calling, reusing the existing Anthropic client/model helpers from
modules.retrieval.service (get_anthropic_client, get_synthesis_model)
rather than building a second Anthropic client or duplicating auth/model-
validation logic. That module is not modified - only its two public
functions are imported.

anthropic==0.25.x (pinned by pyproject.toml) has no `tools`/`tool_choice`
support on the stable client.messages.create() - tool use is only reachable
via the beta endpoint client.beta.tools.messages.create(), with tool_choice
forced through extra_body (identical constraint to
modules.ai.triage.classifier and modules.query_understanding.service).

Unlike modules.retrieval.service.synthesize_answer() (which streams), this
call is non-streaming: single-turn grounded answering with a forced tool
call has no chat surface to stream tokens into and tool-use responses are
not incrementally useful anyway.
"""
from __future__ import annotations

import anthropic
from pydantic import ValidationError

from modules.answering.prompt_builder import ANSWER_TOOL_NAME, ANSWER_TOOL_SCHEMA
from modules.answering.schemas import AnswerToolOutput
from modules.retrieval.service import get_anthropic_client, get_synthesis_model

MAX_TOKENS = 1024
TEMPERATURE = 0
REQUEST_TIMEOUT_SECONDS = 30.0


class AnswerProviderError(Exception):
    """Base class for all generate_completion() failures raised by this module."""


class AnswerAPIError(AnswerProviderError):
    """The underlying Anthropic API call failed (HTTP error, timeout, connection)."""


class AnswerToolCallError(AnswerProviderError):
    """Claude did not return the expected forced tool-use block."""


class AnswerResponseValidationError(AnswerProviderError):
    """The tool_use input did not validate against AnswerToolOutput."""


async def generate_completion(system_prompt: str, user_message: str) -> tuple[AnswerToolOutput, str]:
    """Call Claude once with system_prompt/user_message; return (tool_output, model).

    Raises AnswerAPIError if the Anthropic API call fails (including
    RuntimeError from get_anthropic_client()/get_synthesis_model() for
    missing/invalid configuration), AnswerToolCallError if Claude doesn't
    return the forced submit_answer tool call, or
    AnswerResponseValidationError if the tool input fails schema
    validation.
    """
    try:
        client = get_anthropic_client()
        model = get_synthesis_model()
    except RuntimeError as exc:
        raise AnswerAPIError(f"Anthropic configuration error: {exc}") from exc

    try:
        message = await client.beta.tools.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=[ANSWER_TOOL_SCHEMA],
            extra_body={"tool_choice": {"type": "tool", "name": ANSWER_TOOL_NAME}},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except anthropic.APITimeoutError as exc:
        raise AnswerAPIError(f"Anthropic answer call timed out: {exc}") from exc
    except anthropic.APIError as exc:
        raise AnswerAPIError(f"Anthropic answer call failed: {exc}") from exc

    tool_use_block = next(
        (block for block in message.content if getattr(block, "type", None) == "tool_use"),
        None,
    )
    if tool_use_block is None:
        raise AnswerToolCallError("Claude did not return a tool_use block for the answer call.")
    if tool_use_block.name != ANSWER_TOOL_NAME:
        raise AnswerToolCallError(
            f"Claude called tool '{tool_use_block.name}', expected '{ANSWER_TOOL_NAME}'."
        )

    try:
        tool_output = AnswerToolOutput.model_validate(tool_use_block.input)
    except ValidationError as exc:
        raise AnswerResponseValidationError(f"Answer tool input failed validation: {exc}") from exc

    return tool_output, model
