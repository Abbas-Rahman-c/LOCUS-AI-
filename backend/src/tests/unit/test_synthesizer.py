"""Unit tests for modules.retrieval.synthesis.synthesizer -- Anthropic client mocked."""
from __future__ import annotations

from uuid import uuid4

import pytest

from modules.retrieval.schemas import RankedDecision, RetrievedDecision
from modules.retrieval.synthesis import synthesizer
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


def _ranked(decision_id, statement="Move to 3 pricing tiers") -> RankedDecision:
    return RankedDecision(
        decision=RetrievedDecision(
            decision_id=decision_id,
            tenant_id=TENANT,
            decision_statement=statement,
            status="decided",
            record_type="decision",
        ),
        rrf_score=0.5,
        rank=1,
    )


@pytest.mark.asyncio
async def test_synthesize_answer_maps_cited_label_back_to_decision_id():
    decision_id = uuid4()
    client = FakeAnthropicClient(
        make_tool_use_message(
            "submit_answer",
            {"answer": "We moved to 3 tiers. [D1]", "cited_labels": ["D1"], "no_relevant_decisions": False},
        )
    )
    result = await synthesizer.synthesize_answer(
        "what did we decide about pricing",
        TENANT,
        [_ranked(decision_id)],
        client=client,
        model="claude-test",
        resolve_permalinks=False,
    )
    assert result.answer_text == "We moved to 3 tiers. [D1]"
    assert result.cited_decision_ids == [decision_id]
    assert result.grounded_in == [decision_id]


@pytest.mark.asyncio
async def test_synthesize_answer_empty_candidates_short_circuits_without_api_call():
    client = FakeAnthropicClient(make_tool_use_message("submit_answer", {}))
    result = await synthesizer.synthesize_answer("unanswerable question", TENANT, [], client=client)
    assert result.citations == []
    assert result.grounded_in == []
    assert client.messages.calls == []  # never called Sonnet


@pytest.mark.asyncio
async def test_synthesize_answer_drops_unknown_label_instead_of_raising():
    decision_id = uuid4()
    client = FakeAnthropicClient(
        make_tool_use_message(
            "submit_answer",
            {"answer": "answer text", "cited_labels": ["D99"], "no_relevant_decisions": False},
        )
    )
    result = await synthesizer.synthesize_answer(
        "q", TENANT, [_ranked(decision_id)], client=client, resolve_permalinks=False
    )
    assert result.citations == []


@pytest.mark.asyncio
async def test_synthesize_answer_no_relevant_decisions_flag_empties_citations():
    decision_id = uuid4()
    client = FakeAnthropicClient(
        make_tool_use_message(
            "submit_answer",
            {"answer": "No decision found.", "cited_labels": ["D1"], "no_relevant_decisions": True},
        )
    )
    result = await synthesizer.synthesize_answer(
        "q", TENANT, [_ranked(decision_id)], client=client, resolve_permalinks=False
    )
    assert result.citations == []


@pytest.mark.asyncio
async def test_synthesize_answer_raises_on_missing_tool_call():
    from types import SimpleNamespace

    client = FakeAnthropicClient(SimpleNamespace(content=[], stop_reason="end_turn"))
    with pytest.raises(synthesizer.SynthesisResponseError):
        await synthesizer.synthesize_answer("q", TENANT, [_ranked(uuid4())], client=client)


@pytest.mark.asyncio
async def test_synthesize_answer_sends_forced_tool_choice():
    client = FakeAnthropicClient(
        make_tool_use_message(
            "submit_answer", {"answer": "a", "cited_labels": [], "no_relevant_decisions": True}
        )
    )
    await synthesizer.synthesize_answer("q", TENANT, [_ranked(uuid4())], client=client, resolve_permalinks=False)
    call = client.messages.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "submit_answer"}
    assert "[D1]" in call["messages"][0]["content"]
