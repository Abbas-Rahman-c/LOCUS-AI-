"""
Answer synthesis prompt -- grounded in retrieved decisions, no hallucination.

Builds the system + user messages modules.retrieval.synthesis.synthesizer
sends to Sonnet, plus the forced-tool-use schema that gets a structured,
reliably-parseable answer back (rather than scraping citation markers out
of free text). The user message labels each retrieved decision [D1], [D2],
... and the model is required to cite using those labels in `cited_labels`
-- synthesizer.py maps labels back to decision_id, so citation extraction
never depends on the model getting UUID formatting right in prose.
"""
from __future__ import annotations

from uuid import UUID

from modules.retrieval.schemas import RankedDecision

SYSTEM_PROMPT = """You are Locus AI's answer synthesizer. You answer questions about decisions \
a team has made, using ONLY the decision records provided to you below -- never prior \
knowledge, never assumptions about what a team "probably" decided.

Rules, in order of importance:
1. GROUNDING: every claim in your answer must be directly supported by at least one \
provided decision record. Do not infer, extrapolate, or fill gaps with plausible-sounding \
detail that isn't in the records.
2. HONEST NEGATIVES: if none of the provided decisions actually answer the question, say \
so plainly (e.g. "There's no recorded decision about X yet") instead of stretching a \
loosely related decision to fit. Set no_relevant_decisions=true in that case and cite nothing.
3. STATUS AWARENESS: a decision with status "superseded" was later replaced -- do not \
present it as current unless the question is explicitly about history. Prefer the \
superseding decision when both are present.
4. CITE WHAT YOU USE: cited_labels must list every decision label (e.g. "D1") your answer \
actually relies on, and must not list labels you didn't use. A label appearing in the \
provided records but not needed for the answer should not be cited just because it's \
topically related.
5. BE CONCISE: answer the question directly in 1-4 sentences. This is a decision lookup, \
not a report."""


TOOL_NAME = "submit_answer"

SYNTHESIS_TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": "Submit the synthesized, grounded answer to the user's question.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "The grounded answer to the question, citing decisions inline by label, e.g. '[D1]'.",
            },
            "cited_labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Every decision label (e.g. 'D1') the answer actually relies on. Empty if no_relevant_decisions is true.",
            },
            "no_relevant_decisions": {
                "type": "boolean",
                "description": "True if none of the provided decisions answer the question.",
            },
        },
        "required": ["answer", "cited_labels", "no_relevant_decisions"],
    },
}


def _label(index: int) -> str:
    return f"D{index}"


def build_decision_labels(ranked: list[RankedDecision]) -> dict[str, UUID]:
    """Stable label -> decision_id map, in the same order the decisions are
    shown to the model. Built once and reused for both the prompt and
    parsing the model's cited_labels back to UUIDs."""
    return {_label(i + 1): r.decision.decision_id for i, r in enumerate(ranked)}


def build_user_message(query: str, ranked: list[RankedDecision]) -> str:
    if not ranked:
        return (
            f"Question: {query}\n\n"
            "No decision records were retrieved for this question. Answer that no relevant "
            "decision was found, set no_relevant_decisions=true, and cite nothing."
        )

    lines = [f"Question: {query}", "", "Retrieved decision records:"]
    for i, r in enumerate(ranked):
        d = r.decision
        lines.append(f"\n[{_label(i + 1)}] status={d.status} record_type={d.record_type}")
        lines.append(f"Statement: {d.decision_statement}")
        if d.rationale:
            lines.append(f"Rationale: {d.rationale}")
    return "\n".join(lines)
