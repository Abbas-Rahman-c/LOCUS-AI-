"""
Haiku triage prompt — recall-biased, contrastive few-shot examples.

Classifies a single ingested event as KEEP / UNCERTAIN / DISCARD before the
(more expensive) extraction stage runs. Recall-biased: when the model can't
tell whether an event matters, it must choose UNCERTAIN over DISCARD — a
wrongly discarded decision is lost permanently, while UNCERTAIN only costs
one extra review pass.
"""
from __future__ import annotations

import json

from modules.ai.triage.schemas import TriageDecision, TriageReasonCode
from modules.ingestion.envelope.schemas import EventEnvelope

TRIAGE_TOOL_NAME = "record_triage_result"

SYSTEM_PROMPT = """You are the triage stage of Locus AI, a decision-intelligence system \
that extracts durable decisions, action items, and blockers from day-to-day \
workplace communication (Slack, Gmail, Notion).

Your only job is to classify ONE event as KEEP, UNCERTAIN, or DISCARD, using \
only the text of that event below. Do not infer facts, participants, prior \
messages, or outcomes that are not stated in the event itself — you have no \
access to surrounding conversation or any other context.

Decision rules:

KEEP — the event contains at least one of:
  - a clear decision that was made
  - an action item with an identifiable owner or commitment
  - a blocker that is preventing progress
  - a confirmed change (e.g. to a plan, schedule, scope, or system)
  - an ownership assignment or deadline
  - an operational commitment ("we will...", "I'll have this done by...")

UNCERTAIN — the event might matter but is incomplete on its own:
  - a tentative proposal that has not been confirmed
  - something explicitly awaiting approval or sign-off
  - language that is ambiguous about whether a decision was actually reached
  - a statement whose relevance depends on missing context you don't have
  When you cannot confidently tell whether an event is KEEP or DISCARD, \
choose UNCERTAIN. Never guess DISCARD just because you are unsure.

DISCARD — the event is clearly NOT decision-relevant:
  - a greeting, thank-you, or other social chatter
  - an emoji reaction or acknowledgement with no new content
  - a newsletter, digest, or marketing content
  - a reminder or automated/bot notification
  - spam
  - content unrelated to any decision, action item, or blocker

Do not classify by keyword-matching alone. The presence of a word like \
"decide" does not by itself mean KEEP, and the presence of "hi" does not by \
itself mean DISCARD — read the event's actual meaning in context.

Call the `record_triage_result` tool exactly once with your decision, a \
confidence score between 0 and 1, and the single reason_code that best \
explains your decision."""


def build_user_message(event: EventEnvelope) -> str:
    """Render the event as the single user-turn Claude sees — no other context.

    raw_content is a dict (e.g. Gmail's {"subject", "body"}), not free text -
    rendered as JSON so every key the connector populated is visible to the
    model without guessing a source-specific text extraction.
    """
    thread_ref = event.thread_ref or "(none)"
    return (
        f"source: {event.source}\n"
        f"actor: {event.actor}\n"
        f"thread_ref: {thread_ref}\n"
        f"permission_scope: {event.permission_scope}\n"
        f"content:\n{json.dumps(event.raw_content, default=str)}"
    )


TRIAGE_TOOL_SCHEMA = {
    "name": TRIAGE_TOOL_NAME,
    "description": (
        "Record the triage decision for one event: whether it should be KEPT for "
        "extraction, DISCARDed as not decision-relevant, or is UNCERTAIN."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "decision": {
                "type": "string",
                "enum": [d.value for d in TriageDecision],
                "description": "KEEP, UNCERTAIN, or DISCARD.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence in the decision, between 0 and 1.",
            },
            "reason_code": {
                "type": "string",
                "enum": [r.value for r in TriageReasonCode],
                "description": "The single reason code that best explains the decision.",
            },
        },
        "required": ["decision", "confidence", "reason_code"],
        "additionalProperties": False,
    },
}
