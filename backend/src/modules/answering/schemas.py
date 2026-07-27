"""
Answering schemas — strict Pydantic v2 contracts for single-turn grounded
question answering (Claude Answer Service).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AnswerToolOutput(BaseModel):
    """Validated shape of the submit_answer tool call's input - Claude's raw, unenforced output."""

    model_config = ConfigDict(extra="forbid")

    sufficient_evidence: bool
    answer: str
    reasoning: str
    citations: list[int] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


class AnswerResult(BaseModel):
    """generate_answer()'s return value.

    answer/citations are enforced (not just Claude's raw output): whenever
    sufficient_evidence is False, modules.answering.service overrides
    answer to the exact REFUSAL_TEXT and citations to [], regardless of
    what Claude's tool call contained - see that module for why.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str
    reasoning: str
    citations: list[int] = Field(default_factory=list)
    confidence: float
    sufficient_evidence: bool
    model: str
    latency_ms: float
