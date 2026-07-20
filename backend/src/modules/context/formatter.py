"""
Context Formatter — pure, deterministic decision -> text rendering for
modules.context.service.build_context().

No Claude calls, no summarization, no fabricated content: every field
either comes directly from the input decision or is rendered as an
explicit placeholder (never invented text) when absent. Same input always
produces the exact same output string.
"""
from __future__ import annotations

from modules.context.schemas import AuthorizedDecisionInput

DIVIDER = "-" * 50
_RATIONALE_NOT_PROVIDED = "Not provided"
_NO_ALTERNATIVES = "None"

# Rough, tokenizer-free heuristic (~4 characters per token for English
# text) - good enough to flag context overflow risk before a real Claude
# call, not an exact token count.
_CHARS_PER_TOKEN = 4


def _format_confidence(confidence: float) -> str:
    return f"{round(confidence * 100)}%"


def _decision_block_lines(index: int, decision: AuthorizedDecisionInput) -> list[str]:
    """Lines for one decision block, 1-indexed to match the 'Decision N' heading."""
    lines = [
        "",
        f"Decision {index}",
        "",
        "Decision:",
        decision.decision_statement,
        "",
        "Reason:",
        decision.rationale if decision.rationale else _RATIONALE_NOT_PROVIDED,
        "",
        "Alternatives:",
        ", ".join(decision.alternatives) if decision.alternatives else _NO_ALTERNATIVES,
        "",
        "Confidence:",
        _format_confidence(decision.confidence),
    ]
    if decision.created_at:
        lines += ["", "Timestamp:", decision.created_at]
    if decision.decision_type:
        lines += ["", "Decision Type:", decision.decision_type]
    if decision.owner:
        lines += ["", "Owner:", decision.owner]
    lines += ["", DIVIDER]
    return lines


def format_context(decisions: list[AuthorizedDecisionInput]) -> str:
    """Render every decision into one divider-separated context string.

    Deterministic: the same decisions always produce the exact same
    string, field-for-field. An empty list renders as a single divider
    with no decision blocks.
    """
    lines = [DIVIDER]
    for index, decision in enumerate(decisions, start=1):
        lines.extend(_decision_block_lines(index, decision))
    return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    """Approximate token count for text, using a ~4-chars-per-token heuristic."""
    return len(text) // _CHARS_PER_TOKEN
