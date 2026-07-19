"""Unit tests for modules.retrieval.evaluation.llm_judge -- Anthropic client mocked."""
from __future__ import annotations

from uuid import uuid4

import pytest

from modules.retrieval.evaluation import llm_judge
from modules.retrieval.schemas import RetrievedDecision
from tests.fixtures.fakes import FakeAnthropicClient, make_tool_use_message

TENANT = uuid4()


@pytest.fixture(autouse=True)
def _anthropic_env(monkeypatch):
    # get_anthropic_model()/get_anthropic_client() are only reached as a
    # fallback when a test doesn't pass model=/client= explicitly -- these
    # tests always pass a fake client, but a couple omit `model=` to also
    # exercise the "use the configured default" code path.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test-model")


def _decision(statement="Move to 3 pricing tiers") -> RetrievedDecision:
    return RetrievedDecision(
        decision_id=uuid4(), tenant_id=TENANT, decision_statement=statement,
        status="decided", record_type="decision",
    )


@pytest.mark.asyncio
async def test_judge_answer_normalizes_scores_to_unit_interval():
    client = FakeAnthropicClient(
        make_tool_use_message(
            "submit_judgment",
            {
                "groundedness_score": 5,
                "groundedness_rationale": "fully supported",
                "correctness_score": 1,
                "correctness_rationale": "wrong",
            },
        )
    )
    score = await llm_judge.judge_answer("q", "reference", "generated", [_decision()], [], client=client)
    assert score.groundedness == 1.0
    assert score.correctness == 0.0


@pytest.mark.asyncio
async def test_judge_answer_midpoint_score():
    client = FakeAnthropicClient(
        make_tool_use_message(
            "submit_judgment",
            {
                "groundedness_score": 3,
                "groundedness_rationale": "partial",
                "correctness_score": 3,
                "correctness_rationale": "partial",
            },
        )
    )
    score = await llm_judge.judge_answer("q", "reference", "generated", [], [], client=client)
    assert score.groundedness == pytest.approx(0.5)
    assert score.correctness == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_judge_answer_out_of_range_score_raises():
    client = FakeAnthropicClient(
        make_tool_use_message(
            "submit_judgment",
            {
                "groundedness_score": 9,
                "groundedness_rationale": "x",
                "correctness_score": 3,
                "correctness_rationale": "y",
            },
        )
    )
    with pytest.raises(llm_judge.JudgeResponseError):
        await llm_judge.judge_answer("q", "ref", "gen", [], [], client=client)


@pytest.mark.asyncio
async def test_judge_answer_missing_tool_call_raises():
    from types import SimpleNamespace

    client = FakeAnthropicClient(SimpleNamespace(content=[], stop_reason="end_turn"))
    with pytest.raises(llm_judge.JudgeResponseError):
        await llm_judge.judge_answer("q", "ref", "gen", [], [], client=client)
