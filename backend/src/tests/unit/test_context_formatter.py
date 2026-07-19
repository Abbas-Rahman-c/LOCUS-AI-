"""
Unit tests for modules.context.formatter. Pure functions, no mocking
required: format_context() and estimate_tokens().
"""
from __future__ import annotations

from modules.context.formatter import DIVIDER, estimate_tokens, format_context
from modules.context.schemas import AuthorizedDecisionInput


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
    def test_returns_only_the_divider(self):
        assert format_context([]) == DIVIDER


class TestOneDecision:
    def test_renders_expected_fields_in_order(self):
        context = format_context([_decision()])
        assert context == "\n".join(
            [
                DIVIDER,
                "",
                "Decision 1",
                "",
                "Decision:",
                "Use Stripe instead of Paddle",
                "",
                "Reason:",
                "Supports self-service billing",
                "",
                "Alternatives:",
                "Paddle",
                "",
                "Confidence:",
                "94%",
                "",
                DIVIDER,
            ]
        )


class TestMultipleDecisions:
    def test_renders_each_decision_heading_in_order(self):
        decisions = [
            _decision(decision_statement="Use Stripe"),
            _decision(decision_statement="Use Postgres"),
            _decision(decision_statement="Use FastAPI"),
        ]
        context = format_context(decisions)
        assert context.index("Decision 1") < context.index("Decision 2") < context.index(
            "Decision 3"
        )
        assert context.count(DIVIDER) == len(decisions) + 1


class TestMissingRationale:
    def test_none_rationale_becomes_not_provided_placeholder(self):
        context = format_context([_decision(rationale=None)])
        assert "Reason:\nNot provided" in context

    def test_placeholder_is_not_a_fabricated_explanation(self):
        context = format_context([_decision(rationale=None)])
        assert "Supports self-service billing" not in context


class TestMissingAlternatives:
    def test_empty_alternatives_becomes_none_placeholder(self):
        context = format_context([_decision(alternatives=[])])
        assert "Alternatives:\nNone" in context

    def test_multiple_alternatives_are_comma_joined(self):
        context = format_context([_decision(alternatives=["Paddle", "Chargebee"])])
        assert "Alternatives:\nPaddle, Chargebee" in context


class TestConfidenceFormatting:
    def test_ninety_four_percent(self):
        assert "Confidence:\n94%" in format_context([_decision(confidence=0.94)])

    def test_full_confidence(self):
        assert "Confidence:\n100%" in format_context([_decision(confidence=1.0)])

    def test_zero_confidence(self):
        assert "Confidence:\n0%" in format_context([_decision(confidence=0.0)])


class TestTimestampAndOwnerOptional:
    def test_timestamp_included_when_present(self):
        context = format_context([_decision(created_at="2026-07-19T00:00:00Z")])
        assert "Timestamp:\n2026-07-19T00:00:00Z" in context

    def test_timestamp_absent_when_missing(self):
        assert "Timestamp:" not in format_context([_decision(created_at=None)])

    def test_owner_included_when_present(self):
        assert "Owner:\nJane Doe" in format_context([_decision(owner="Jane Doe")])

    def test_owner_absent_when_unresolved(self):
        assert "Owner:" not in format_context([_decision(owner=None)])


class TestFormattingConsistency:
    def test_same_input_produces_identical_output(self):
        decisions = [_decision(), _decision(decision_statement="Use Postgres")]
        assert format_context(decisions) == format_context(decisions)


class TestTokenEstimation:
    def test_estimate_uses_four_chars_per_token_heuristic(self):
        assert estimate_tokens("a" * 40) == 10

    def test_empty_string_is_zero_tokens(self):
        assert estimate_tokens("") == 0

    def test_estimate_grows_with_context_length(self):
        short_context = format_context([_decision()])
        long_context = format_context([_decision(), _decision(), _decision()])
        assert estimate_tokens(long_context) > estimate_tokens(short_context)
