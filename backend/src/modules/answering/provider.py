"""
Claude Answer Provider — plain single-turn text completion, reusing the
existing Anthropic client/model helpers from modules.retrieval.service
(get_anthropic_client, get_synthesis_model) rather than building a second
Anthropic client or duplicating auth/model-validation logic. That module
is not modified - only its two public functions are imported.

Unlike modules.retrieval.service.synthesize_answer() (which streams),
this call is non-streaming (client.messages.create(), stream not set):
single-turn grounded answering has no chat surface to stream tokens into.
"""
from __future__ import annotations

import anthropic

from modules.retrieval.service import get_anthropic_client, get_synthesis_model

MAX_TOKENS = 1024
TEMPERATURE = 0


class AnswerProviderError(Exception):
    """Base class for all generate_completion() failures raised by this module."""


class AnswerAPIError(AnswerProviderError):
    """The underlying Anthropic API call failed (HTTP error, timeout, connection)."""


class AnswerResponseValidationError(AnswerProviderError):
    """Claude's response did not contain the expected text content block."""


async def generate_completion(system_prompt: str, user_message: str) -> tuple[str, str]:
    """Call Claude once with system_prompt/user_message; return (answer_text, model).

    Raises AnswerAPIError if the Anthropic API call fails (including
    RuntimeError from get_anthropic_client()/get_synthesis_model() for
    missing/invalid configuration), or AnswerResponseValidationError if
    the response contains no text block.
    """
    try:
        client = get_anthropic_client()
        model = get_synthesis_model()
    except RuntimeError as exc:
        raise AnswerAPIError(f"Anthropic configuration error: {exc}") from exc

    try:
        message = await client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APITimeoutError as exc:
        raise AnswerAPIError(f"Anthropic answer call timed out: {exc}") from exc
    except anthropic.APIError as exc:
        raise AnswerAPIError(f"Anthropic answer call failed: {exc}") from exc

    text_block = next(
        (block for block in message.content if getattr(block, "type", None) == "text"),
        None,
    )
    if text_block is None:
        raise AnswerResponseValidationError("Claude did not return a text content block.")

    return text_block.text, model
