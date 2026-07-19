"""
Calls Sonnet with retrieved decisions; returns a grounded, cited answer.

Uses forced tool-use (tool_choice={"type": "tool", "name": "submit_answer"})
rather than parsing free text, so citation extraction is a dict lookup
against modules.ai.prompts.synthesis_prompt.build_decision_labels()'s
label map, not a regex over prose. If Sonnet cites a label that isn't in
that map (shouldn't happen given forced tool use + an explicit label list
in the prompt, but "shouldn't happen" is not a guarantee), that label is
dropped rather than raising -- an answer with fewer citations than the
model intended is a smaller failure than the whole request erroring out.
"""
from __future__ import annotations

import logging
from uuid import UUID

import anthropic
import asyncpg

from common.config.anthropic_config import get_anthropic_client, get_anthropic_model
from modules.ai.prompts.synthesis_prompt import (
    SYNTHESIS_TOOL_SCHEMA,
    SYSTEM_PROMPT,
    TOOL_NAME,
    build_decision_labels,
    build_user_message,
)
from modules.retrieval.citations.resolver import resolve_citations
from modules.retrieval.schemas import Citation, RankedDecision, SynthesizedAnswer

log = logging.getLogger(__name__)

MAX_TOKENS = 1024


class SynthesisError(Exception):
    """Raised when the Sonnet call itself fails."""


class SynthesisResponseError(SynthesisError):
    """Raised when Sonnet's response doesn't contain the expected tool call."""


def _extract_tool_input(message: anthropic.types.Message) -> dict:
    for block in message.content:
        if block.type == "tool_use" and block.name == TOOL_NAME:
            return block.input
    raise SynthesisResponseError(
        f"Sonnet response contained no '{TOOL_NAME}' tool_use block (stop_reason={message.stop_reason!r})"
    )


async def synthesize_answer(
    query: str,
    tenant_id: UUID,
    ranked: list[RankedDecision],
    *,
    client: anthropic.AsyncAnthropic | None = None,
    model: str | None = None,
    resolve_permalinks: bool = True,
    pool: asyncpg.Pool | None = None,
) -> SynthesizedAnswer:
    """Synthesizes a grounded answer over `ranked` (the RRF-fused, already
    tenant-scoped candidate list from modules.retrieval.pipeline).

    Empty `ranked` is valid -- it's exactly the negative-example case
    (scenario_packs.json's QuestionCategory.NEGATIVE) -- and short-circuits
    to a "no relevant decisions" answer without calling Sonnet at all.

    Raises SynthesisError if the Anthropic API call fails, SynthesisResponseError
    if the response doesn't contain the expected structured tool call.
    """
    if not ranked:
        return SynthesizedAnswer(
            query=query,
            tenant_id=tenant_id,
            answer_text="There's no recorded decision that answers this question.",
            citations=[],
            grounded_in=[],
        )

    anthropic_client = client if client is not None else get_anthropic_client()
    model_name = model if model is not None else get_anthropic_model()

    label_map = build_decision_labels(ranked)
    user_message = build_user_message(query, ranked)

    try:
        response = await anthropic_client.messages.create(
            model=model_name,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=[SYNTHESIS_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": TOOL_NAME},
        )
    except anthropic.APIError as exc:
        raise SynthesisError(f"Sonnet synthesis call failed: {type(exc).__name__}: {exc}") from exc

    tool_input = _extract_tool_input(response)

    answer_text = tool_input.get("answer", "").strip()
    if not answer_text:
        raise SynthesisResponseError("Sonnet returned an empty answer")

    no_relevant = bool(tool_input.get("no_relevant_decisions", False))
    cited_labels = [] if no_relevant else tool_input.get("cited_labels", [])

    cited_decision_ids: list[UUID] = []
    for label in cited_labels:
        decision_id = label_map.get(label)
        if decision_id is None:
            log.warning("Sonnet cited unknown label %r; dropping", label)
            continue
        if decision_id not in cited_decision_ids:
            cited_decision_ids.append(decision_id)

    grounded_in = [r.decision.decision_id for r in ranked]

    citations = (
        await resolve_citations(cited_decision_ids, tenant_id, pool=pool)
        if resolve_permalinks and cited_decision_ids
        else [Citation(decision_id=d, permalink=None) for d in cited_decision_ids]
    )

    log.info(
        "synthesize_answer tenant_id=%s candidates=%d cited=%d no_relevant=%s",
        tenant_id, len(ranked), len(citations), no_relevant,
    )

    return SynthesizedAnswer(
        query=query,
        tenant_id=tenant_id,
        answer_text=answer_text,
        citations=citations,
        grounded_in=grounded_in,
    )
