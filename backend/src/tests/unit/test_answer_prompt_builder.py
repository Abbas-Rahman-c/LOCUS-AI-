"""
Unit tests for modules.answering.prompt_builder. Pure string construction,
no mocking required.
"""
from __future__ import annotations

from modules.answering.prompt_builder import SYSTEM_PROMPT, build_user_message


class TestSystemPrompt:
    def test_identifies_as_locus_ai(self):
        assert "You are Locus AI." in SYSTEM_PROMPT

    def test_instructs_context_only_answering(self):
        assert "Answer ONLY from the supplied context." in SYSTEM_PROMPT
        assert "Do not invent information." in SYSTEM_PROMPT

    def test_contains_exact_refusal_sentence(self):
        assert (
            '"I couldn\'t find enough information in the available decisions."' in SYSTEM_PROMPT
        )

    def test_instructs_citing_decision_numbers(self):
        assert "Always cite the relevant decision numbers." in SYSTEM_PROMPT


class TestPromptFormatting:
    def test_includes_question_and_context_labels(self):
        message = build_user_message("Why did we choose Stripe?", "some context")
        assert message == "Question:\nWhy did we choose Stripe?\n\nContext:\nsome context"

    def test_is_deterministic(self):
        first = build_user_message("Why did we choose Stripe?", "context A")
        second = build_user_message("Why did we choose Stripe?", "context A")
        assert first == second

    def test_large_context_is_passed_through_unmodified(self):
        large_context = "Decision block. " * 5000
        message = build_user_message("Why did we choose Stripe?", large_context)
        assert message.endswith(large_context)
