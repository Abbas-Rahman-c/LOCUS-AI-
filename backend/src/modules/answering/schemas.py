"""
Answering schemas — strict Pydantic v2 contracts for single-turn grounded
question answering (Claude Answer Service).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AnswerResult(BaseModel):
    """generate_answer()'s return value."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[int] = Field(default_factory=list)
    model: str
    latency_ms: float
