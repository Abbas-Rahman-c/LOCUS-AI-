"""
Query Understanding prompt — forced tool call, same pattern as
modules.ai.prompts.triage_prompt: Claude can only respond via the
record_query_analysis tool, never free text.
"""
from __future__ import annotations

QUERY_ANALYSIS_TOOL_NAME = "record_query_analysis"

QUESTION_TYPES = ["why", "what", "when", "who", "list", "summary", "comparison", "other"]

SYSTEM_PROMPT = """You are the query-understanding stage of Locus AI, a decision-intelligence \
system. Before any retrieval happens, analyze the user's question so the retrieval layer can \
find the right decisions.

For the question below, determine:

1. intent — one sentence describing what the user actually wants to know.
2. question_type — the primary form of the question: why, what, when, who, list, summary, \
comparison, or other. ("list"/"summary"/"comparison" mean the user likely wants MULTIPLE \
decisions, not just one.)
3. entities — proper nouns, ticket IDs, filenames, people's names, company/vendor names, and \
acronyms mentioned or clearly implied by the question. Include both the acronym and its likely \
expansion when relevant (e.g. "SSO" and "Single Sign-On").
4. keywords — 3 to 8 high-signal retrieval terms capturing the core topic. Expand with likely \
synonyms and related terms a company's internal decision record might actually use — e.g. if the \
question mentions switching away from a product, include both the old and new product names, the \
general category, and the type of decision (e.g. "Stripe", "Paddle", "billing", "migration", \
"payment provider"). Do not include stopwords, question words, or generic verbs like "update" or \
"decide" unless they are genuinely distinctive to the topic.
5. department_guess — the business domain/department this most likely relates to (e.g. \
engineering, finance, security, legal, hiring, marketing, product, analytics, customer support, \
infrastructure), or an empty string if genuinely unclear.
6. is_multi_document — true if answering this well likely requires citing multiple decisions \
(broad "what have we decided about X" questions, list/summary/comparison questions), false for a \
question about one specific fact or decision.

Call the record_query_analysis tool exactly once with this analysis. Do not answer the question \
itself — you have not been given any decisions to answer from yet."""


def build_user_message(question: str) -> str:
    return f"Question: {question}"


QUERY_ANALYSIS_TOOL_SCHEMA = {
    "name": QUERY_ANALYSIS_TOOL_NAME,
    "description": "Record a structured analysis of the user's question before retrieval runs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": "One sentence describing what the user actually wants to know.",
            },
            "question_type": {
                "type": "string",
                "enum": QUESTION_TYPES,
                "description": "The primary question form.",
            },
            "entities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Proper nouns, ticket IDs, filenames, people, vendor names, acronyms.",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-8 high-signal retrieval terms, expanded with likely synonyms.",
            },
            "department_guess": {
                "type": "string",
                "description": "Best-guess business domain/department, or empty string if unclear.",
            },
            "is_multi_document": {
                "type": "boolean",
                "description": "True if the question likely needs multiple cited decisions.",
            },
        },
        "required": ["intent", "question_type", "entities", "keywords", "department_guess", "is_multi_document"],
        "additionalProperties": False,
    },
}
