"""
Extraction prompt — forced tool-call schema, zero-inference extraction.

Stage 2 of the AI pipeline: given one event that triage already marked KEEP
or UNCERTAIN, pull out the single decision/action_item/blocker it contains.
Every field must trace back to text that is explicitly present in the
event — the model must never invent an owner, a rationale, an alternative,
or an inflated confidence score just because a field is expected.
"""
from __future__ import annotations

import json

from modules.ai.extraction.schemas import ActorRole, DecisionStatus, RecordType
from modules.ingestion.envelope.schemas import EventEnvelope

EXTRACTION_TOOL_NAME = "record_extraction_result"

SYSTEM_PROMPT = """You are the extraction stage of Locus AI, a decision-intelligence system \
that turns workplace communication (Slack, Gmail, Notion) into a durable \
record of decisions, action items, and blockers.

You will be given ONE event that has already been judged worth extracting. \
Using only the text of that event, extract exactly one record: a decision, \
an action item, or a blocker.

Ground rules — extract only what is explicitly present:

  - decision_statement: state the decision, action, or blocker in the \
event's own terms. Do not add detail, context, or consequences that are not \
stated.
  - status: "decided" only if the event states the decision/action is final \
or confirmed. "proposed" if it is tentative, suggested, or awaiting \
approval. "superseded" only if the event explicitly says a prior decision \
was replaced or reversed.
  - rationale: the reason given for the decision/action/blocker, in the \
event's own terms. If no reason is stated, you MUST return null. Never \
invent a plausible-sounding rationale.
  - alternatives_considered: other options the event explicitly says were \
considered or rejected. If none are mentioned, you MUST return an empty \
list. Never invent alternatives that were not mentioned.
  - actors: people the event explicitly names in connection with this \
record.
      - role "decided_by": the event explicitly states this person made \
the decision, owns the action item, or is responsible for resolving the \
blocker. At most one actor may have this role.
      - role "mentioned": the event names this person in connection with \
the record but does not explicitly assign ownership.
      If no actor is named, you MUST return an empty list. Never invent or \
guess an owner who is not explicitly named in the text.
  - confidence: a score between 0 and 1 reflecting how clearly the event's \
text supports the record_type, status, and decision_statement you chose. \
Base it only on how explicit and unambiguous the text is — do not raise it \
to compensate for missing rationale, alternatives, or actors, and do not \
lower it just because those fields are empty; empty fields are a correct, \
expected outcome when the event doesn't mention them.

Call the `record_extraction_result` tool exactly once with the extracted \
record. Return only the structured tool output — no other commentary."""


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


EXTRACTION_TOOL_SCHEMA = {
    "name": EXTRACTION_TOOL_NAME,
    "description": (
        "Record the single decision, action item, or blocker extracted from one event, "
        "using only information explicitly present in that event."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "record_type": {
                "type": "string",
                "enum": [t.value for t in RecordType],
                "description": "decision, action_item, or blocker.",
            },
            "status": {
                "type": "string",
                "enum": [s.value for s in DecisionStatus],
                "description": "proposed, decided, or superseded.",
            },
            "decision_statement": {
                "type": "string",
                "minLength": 1,
                "description": "The core statement being recorded, in the event's own terms.",
            },
            "rationale": {
                "type": ["string", "null"],
                "description": "The stated reason, or null if no reason is given in the event.",
            },
            "alternatives_considered": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Other options explicitly mentioned as considered or rejected. Empty if none.",
            },
            "actors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_actor_id": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Provider-native id of the referenced actor, as it appears in the event.",
                        },
                        "role": {
                            "type": "string",
                            "enum": [r.value for r in ActorRole],
                            "description": "decided_by (at most one actor) or mentioned.",
                        },
                    },
                    "required": ["source_actor_id", "role"],
                    "additionalProperties": False,
                },
                "description": "Actors explicitly named in connection with this record. Empty if none.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence that the extraction is explicitly supported by the event text, 0-1.",
            },
        },
        "required": [
            "record_type",
            "status",
            "decision_statement",
            "alternatives_considered",
            "actors",
            "confidence",
        ],
        "additionalProperties": False,
    },
}
