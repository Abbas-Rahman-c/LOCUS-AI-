"""
Unit tests for modules.ai.pipeline.orchestrator.process_ai_event().

classify() and extract() are mocked at their orchestrator import sites -
this tests only the two-stage sequencing (triage always runs; extraction
runs unless triage discarded), not the Claude calls themselves (covered by
test_triage_classifier.py / test_extractor.py).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from modules.ai.extraction.extractor import ExtractionError
from modules.ai.extraction.schemas import DecisionStatus, ExtractionResult, RecordType
from modules.ai.pipeline.orchestrator import (
    ClassificationStageError,
    ExtractionStageError,
    process_ai_event,
)
from modules.ai.triage.classifier import TriageClassificationError
from modules.ai.triage.schemas import TriageDecision, TriageReasonCode, TriageResult
from modules.ingestion.envelope.schemas import EventEnvelope

pytestmark = pytest.mark.asyncio


def _event() -> EventEnvelope:
    return EventEnvelope(
        tenant_id="13bcd0fa-1ed9-4634-93c7-278ba97ec658",
        source="gmail",
        source_id="18d1234abcd",
        actor="alice@example.com",
        permission_scope=[],
        raw_content={"subject": "Re: pricing", "body": "We decided to ship Friday."},
    )


def _triage(decision: TriageDecision) -> TriageResult:
    return TriageResult(
        decision=decision, confidence=0.9, reason_code=TriageReasonCode.EXPLICIT_DECISION
    )


def _extraction() -> ExtractionResult:
    return ExtractionResult(
        record_type=RecordType.DECISION,
        status=DecisionStatus.DECIDED,
        decision_statement="Ship Friday.",
        confidence=0.9,
    )


class TestKeepRunsExtraction:
    async def test_keep_triage_produces_extraction(self):
        with (
            patch(
                "modules.ai.pipeline.orchestrator.classify",
                AsyncMock(return_value=_triage(TriageDecision.KEEP)),
            ),
            patch(
                "modules.ai.pipeline.orchestrator.extract",
                AsyncMock(return_value=_extraction()),
            ) as extract_mock,
        ):
            result = await process_ai_event(_event())

        assert result.triage.decision == TriageDecision.KEEP
        assert result.extraction is not None
        extract_mock.assert_awaited_once()


class TestUncertainRunsExtraction:
    async def test_uncertain_triage_also_produces_extraction(self):
        """UNCERTAIN must never be silently treated as DISCARD or KEEP."""
        with (
            patch(
                "modules.ai.pipeline.orchestrator.classify",
                AsyncMock(return_value=_triage(TriageDecision.UNCERTAIN)),
            ),
            patch(
                "modules.ai.pipeline.orchestrator.extract",
                AsyncMock(return_value=_extraction()),
            ) as extract_mock,
        ):
            result = await process_ai_event(_event())

        assert result.triage.decision == TriageDecision.UNCERTAIN
        assert result.extraction is not None
        extract_mock.assert_awaited_once()


class TestDiscardSkipsExtraction:
    async def test_discard_triage_skips_extraction_entirely(self):
        with (
            patch(
                "modules.ai.pipeline.orchestrator.classify",
                AsyncMock(return_value=_triage(TriageDecision.DISCARD)),
            ),
            patch("modules.ai.pipeline.orchestrator.extract", AsyncMock()) as extract_mock,
        ):
            result = await process_ai_event(_event())

        assert result.triage.decision == TriageDecision.DISCARD
        assert result.extraction is None
        extract_mock.assert_not_called()


class TestStageFailuresAreWrapped:
    async def test_triage_failure_raises_classification_stage_error(self):
        with patch(
            "modules.ai.pipeline.orchestrator.classify",
            AsyncMock(side_effect=TriageClassificationError("boom")),
        ):
            with pytest.raises(ClassificationStageError):
                await process_ai_event(_event())

    async def test_extraction_failure_raises_extraction_stage_error(self):
        with (
            patch(
                "modules.ai.pipeline.orchestrator.classify",
                AsyncMock(return_value=_triage(TriageDecision.KEEP)),
            ),
            patch(
                "modules.ai.pipeline.orchestrator.extract",
                AsyncMock(side_effect=ExtractionError("boom")),
            ),
        ):
            with pytest.raises(ExtractionStageError):
                await process_ai_event(_event())
