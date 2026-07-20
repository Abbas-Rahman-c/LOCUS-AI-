"""
Unit tests for modules.context.service.build_context().
"""
from __future__ import annotations

import logging

from modules.context.formatter import DIVIDER, estimate_tokens
from modules.context.schemas import AuthorizedDecisionInput, ContextResult
from modules.context.service import build_context


def _decision(**overrides) -> AuthorizedDecisionInput:
    fields = {
        "decision_statement": "Use Stripe instead of Paddle",
        "rationale": "Supports self-service billing",
        "alternatives": ["Paddle"],
        "confidence": 0.94,
        "created_at": None,
    }
    fields.update(overrides)
    return AuthorizedDecisionInput(**fields)


class TestEmptyDecisions:
    def test_returns_zero_decisions_and_divider_only_context(self):
        result = build_context([])
        assert isinstance(result, ContextResult)
        assert result.decision_count == 0
        assert result.context == DIVIDER
        assert result.token_estimate == estimate_tokens(DIVIDER)


class TestMultipleDecisions:
    def test_decision_count_matches_input_length(self):
        decisions = [_decision(decision_statement=f"Decision {i}") for i in range(5)]
        result = build_context(decisions)
        assert result.decision_count == 5
        assert result.token_estimate == estimate_tokens(result.context)


class TestLogging:
    def test_logs_decision_count_token_estimate_and_build_time(self, caplog):
        with caplog.at_level(logging.INFO, logger="modules.context.service"):
            build_context([_decision(), _decision()])

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "decision_count=2" in message
        assert "token_estimate=" in message
        assert "context_build_time_ms=" in message
