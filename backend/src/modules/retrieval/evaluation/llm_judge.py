"""
LLM-judge groundedness/correctness scoring -- replaces a lexical-overlap
scorer (fraction of shared words between generated and reference answers)
with a Sonnet rubric judge. Lexical overlap rewards an answer for reusing
the reference's exact wording and penalizes a correct paraphrase; it also
can't tell "grounded in the wrong decision" from "grounded in the right
one" if both happen to share vocabulary with the reference. A rubric-based
LLM judge reads for meaning instead.

Two independent rubric dimensions, scored 1-5 and normalized to [0, 1]:
  - groundedness: is every claim in the generated answer supported by the
    retrieved decision records it was shown (not by outside knowledge,
    not by decisions that weren't actually retrieved)?
  - correctness: does the generated answer convey the same substantive
    meaning as the human-written reference_answer, allowing for
    paraphrasing and differences in verbosity?

Forced tool-use (same pattern as modules.retrieval.synthesis.synthesizer)
for a reliably parseable score instead of scraping numbers out of prose.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

import anthropic

from common.config.anthropic_config import get_anthropic_client, get_anthropic_model
from modules.retrieval.schemas import RetrievedDecision

log = logging.getLogger(__name__)

MAX_TOKENS = 1024
_SCALE_MIN = 1
_SCALE_MAX = 5

_TOOL_NAME = "submit_judgment"

_SYSTEM_PROMPT = """You are a strict evaluator for a decision-retrieval RAG system. You score one \
generated answer against two independent rubrics. Be skeptical: an answer that "sounds right" but \
adds detail not present in the shown decision records, or drifts from the reference answer's \
substance, should score low even if fluent.

GROUNDEDNESS (1-5): is every factual claim in the generated answer directly supported by the \
"Retrieved decision records" shown below? 5 = fully supported, no unsupported claims. 3 = mostly \
supported but includes at least one unsupported or overstated claim. 1 = the answer is largely \
fabricated or relies on decisions that were not actually shown. If the generated answer correctly \
states that no relevant decision exists AND no relevant decision was in fact shown, that is a 5, \
not a penalty.

CORRECTNESS (1-5): does the generated answer convey the same substantive meaning as the reference \
answer, regardless of exact wording? 5 = fully matches the reference's substance. 3 = partially \
correct, missing or slightly misstating part of the reference. 1 = contradicts the reference or \
answers a different question. A correct "no relevant decision found" generated answer against a \
reference that also says no decision exists is a 5."""

_JUDGE_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": "Submit groundedness and correctness scores for the generated answer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "groundedness_score": {"type": "integer", "minimum": 1, "maximum": 5},
            "groundedness_rationale": {"type": "string"},
            "correctness_score": {"type": "integer", "minimum": 1, "maximum": 5},
            "correctness_rationale": {"type": "string"},
        },
        "required": [
            "groundedness_score",
            "groundedness_rationale",
            "correctness_score",
            "correctness_rationale",
        ],
    },
}


class JudgeError(Exception):
    """Raised when the Sonnet judge call fails."""


class JudgeResponseError(JudgeError):
    """Raised when the judge's response doesn't contain the expected tool call."""


@dataclass
class JudgeScore:
    groundedness: float  # normalized to [0, 1]
    correctness: float  # normalized to [0, 1]
    rationale: str


def _normalize(score: int) -> float:
    return (score - _SCALE_MIN) / (_SCALE_MAX - _SCALE_MIN)


def _build_user_message(
    question: str,
    reference_answer: str,
    generated_answer: str,
    shown_decisions: list[RetrievedDecision],
    cited_decision_ids: list[UUID],
) -> str:
    lines = [f"Question: {question}", "", "Retrieved decision records shown to the answering model:"]
    if not shown_decisions:
        lines.append("(none -- no decisions were retrieved for this question)")
    for i, d in enumerate(shown_decisions, start=1):
        lines.append(f"\n[D{i}] status={d.status}")
        lines.append(f"Statement: {d.decision_statement}")
        if d.rationale:
            lines.append(f"Rationale: {d.rationale}")

    lines += [
        "",
        f"Decisions the generated answer actually cited: {[str(c) for c in cited_decision_ids] or 'none'}",
        "",
        f"Reference answer (ground truth): {reference_answer}",
        "",
        f"Generated answer to evaluate: {generated_answer}",
    ]
    return "\n".join(lines)


def _extract_tool_input(message: anthropic.types.Message) -> dict:
    for block in message.content:
        if block.type == "tool_use" and block.name == _TOOL_NAME:
            return block.input
    raise JudgeResponseError(
        f"Judge response contained no '{_TOOL_NAME}' tool_use block (stop_reason={message.stop_reason!r})"
    )


async def judge_answer(
    question: str,
    reference_answer: str,
    generated_answer: str,
    shown_decisions: list[RetrievedDecision],
    cited_decision_ids: list[UUID],
    *,
    client: anthropic.AsyncAnthropic | None = None,
    model: str | None = None,
) -> JudgeScore:
    """Scores one generated answer. Raises JudgeError/JudgeResponseError on
    API or parsing failure -- runner.py catches these per-example so one
    bad judge call doesn't fail the whole eval run."""
    anthropic_client = client if client is not None else get_anthropic_client()
    model_name = model if model is not None else get_anthropic_model()

    user_message = _build_user_message(
        question, reference_answer, generated_answer, shown_decisions, cited_decision_ids
    )

    try:
        response = await anthropic_client.messages.create(
            model=model_name,
            max_tokens=MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=[_JUDGE_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
        )
    except anthropic.APIError as exc:
        raise JudgeError(f"Sonnet judge call failed: {type(exc).__name__}: {exc}") from exc

    tool_input = _extract_tool_input(response)

    try:
        groundedness_raw = int(tool_input["groundedness_score"])
        correctness_raw = int(tool_input["correctness_score"])
    except (KeyError, TypeError, ValueError) as exc:
        raise JudgeResponseError(f"Malformed judge scores: {exc}") from exc

    for name, value in (("groundedness_score", groundedness_raw), ("correctness_score", correctness_raw)):
        if not (_SCALE_MIN <= value <= _SCALE_MAX):
            raise JudgeResponseError(f"{name}={value} out of range [{_SCALE_MIN}, {_SCALE_MAX}]")

    rationale = (
        f"groundedness: {tool_input.get('groundedness_rationale', '')} | "
        f"correctness: {tool_input.get('correctness_rationale', '')}"
    )

    return JudgeScore(
        groundedness=_normalize(groundedness_raw),
        correctness=_normalize(correctness_raw),
        rationale=rationale,
    )
