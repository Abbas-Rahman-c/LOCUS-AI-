"""
Answer Prompt Builder — deterministic system + user prompt construction for
single-turn grounded question answering over vector-retrieved decisions.

Claude answers only from what's explicitly in the supplied context, cites
decision numbers, and refuses in a fixed sentence when the context doesn't
support an answer.
"""
from __future__ import annotations

SYSTEM_PROMPT = """You are Locus AI.

Answer ONLY from the supplied context.

Do not invent information.

If the answer cannot be found in the supplied context, respond:
"I couldn't find enough information in the available decisions."

Always cite the relevant decision numbers."""


def build_user_message(question: str, context: str) -> str:
    """Render the question and the Context Builder's formatted context as the single user turn."""
    return f"Question:\n{question}\n\nContext:\n{context}"
