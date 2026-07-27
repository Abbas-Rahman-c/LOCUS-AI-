"""
Query Understanding schemas — strict Pydantic v2 contract for the
pre-retrieval analysis call.

QueryAnalysis is deliberately small: everything /search's retrieval layer
needs (a retrieval-optimized query string for embedding, a separate
OR-joined string for full-text search, an entity list for exact-match
boosting, and a multi-document flag for widening candidate_k / prompting
Claude for a structured summary) is derived from `keywords` via computed
properties, rather than asking the model to produce multiple redundant
query strings itself.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class QuestionType(StrEnum):
    """Mirrors modules.query_understanding.prompt.QUESTION_TYPES exactly."""

    WHY = "why"
    WHAT = "what"
    WHEN = "when"
    WHO = "who"
    LIST = "list"
    SUMMARY = "summary"
    COMPARISON = "comparison"
    OTHER = "other"


class QueryAnalysis(BaseModel):
    """Validated output of the query-understanding tool call for one question."""

    model_config = ConfigDict(extra="forbid")

    intent: str = Field(..., min_length=1, description="One sentence describing what the user actually wants.")
    question_type: QuestionType
    entities: list[str] = Field(default_factory=list, description="Proper nouns, ticket IDs, filenames, people, vendor names, acronyms.")
    keywords: list[str] = Field(default_factory=list, description="3-8 high-signal retrieval terms, expanded with likely synonyms.")
    department_guess: str = Field(default="", description="Best-guess business domain/department, or empty string if unclear.")
    is_multi_document: bool = Field(default=False, description="True if the question likely needs multiple cited decisions.")

    @property
    def rewritten_query(self) -> str:
        """Keyword-dense string to embed INSTEAD OF the raw question.

        Space-joined so it reads naturally to an embedding model; falls
        back to an empty string (never None) when Claude produced no
        keywords, so callers can uniformly do `analysis.rewritten_query or
        original_question` without a None check.
        """
        return " ".join(self.keywords)

    @property
    def keyword_search_query(self) -> str:
        """OR-joined string for websearch_to_tsquery().

        websearch_to_tsquery implicitly ANDs every term in its input. A raw
        natural-language question ANDs words like "update"/"the"/"about"
        that are never in the target decision's stored text, which is the
        root cause of keyword_only's low recall on the 273-decision
        benchmark (documented in the Stage 2/3 evaluation's failure
        analysis). OR-joining just the extracted keywords keeps AND/OR
        control in our hands instead of the raw phrasing.
        """
        return " OR ".join(self.keywords)


NULL_QUERY_ANALYSIS = QueryAnalysis(
    intent="unanalyzed", question_type=QuestionType.OTHER, entities=[], keywords=[],
    department_guess="", is_multi_document=False,
)
