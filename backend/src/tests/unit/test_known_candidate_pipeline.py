"""Unit tests for modules.retrieval.evaluation.known_candidate_pipeline -- Anthropic client mocked."""
from __future__ import annotations

from uuid import uuid4

import pytest

from modules.retrieval.evaluation.golden_dataset import ScenarioDecision
from modules.retrieval.evaluation.known_candidate_pipeline import KnownCandidateRAGPipeline
from tests.fixtures.fakes import FakeAnthropicClient, make_tool_use_message

TENANT = uuid4()
OTHER_TENANT = uuid4()


@pytest.fixture(autouse=True)
def _anthropic_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test-model")


def _decisions() -> list[ScenarioDecision]:
    return [
        ScenarioDecision(
            decision_id=uuid4(),
            tenant_id=TENANT,
            record_type="decision",
            status="decided",
            decision_statement="Move to 3 pricing tiers",
            rationale="Reduces confusion",
            source_permalink="https://example.internal/pricing",
            distractor_type="none",
        ),
        ScenarioDecision(
            decision_id=uuid4(),
            tenant_id=OTHER_TENANT,  # different tenant -- must never surface
            record_type="decision",
            status="decided",
            decision_statement="Cross tenant decision",
            rationale=None,
            source_permalink=None,
            distractor_type="cross_tenant",
        ),
    ]


@pytest.mark.asyncio
async def test_retrieve_filters_to_matching_tenant_only():
    pipeline = KnownCandidateRAGPipeline(decisions=_decisions())
    result = await pipeline.retrieve("pricing question", TENANT, top_k=10)
    assert len(result.ranked) == 1
    assert result.ranked[0].decision.tenant_id == TENANT


@pytest.mark.asyncio
async def test_answer_calls_real_synthesizer_and_fills_known_permalink(monkeypatch):
    decisions = _decisions()
    pipeline = KnownCandidateRAGPipeline(decisions=decisions)

    client = FakeAnthropicClient(
        make_tool_use_message(
            "submit_answer",
            {"answer": "Moved to 3 tiers. [D1]", "cited_labels": ["D1"], "no_relevant_decisions": False},
        )
    )

    import modules.retrieval.evaluation.known_candidate_pipeline as kcp_module

    async def _fake_synthesize(query, tenant_id, ranked, **kwargs):
        from modules.retrieval.synthesis.synthesizer import synthesize_answer as real_synth

        return await real_synth(query, tenant_id, ranked, client=client, resolve_permalinks=False)

    monkeypatch.setattr(kcp_module, "synthesize_answer", _fake_synthesize)

    result = await pipeline.answer("what did we decide about pricing", TENANT, top_k=10)
    assert len(result.citations) == 1
    assert result.citations[0].permalink == "https://example.internal/pricing"
    assert client.messages.calls  # real (faked) Anthropic call was made
