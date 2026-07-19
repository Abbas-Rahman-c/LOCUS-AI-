"""
Context Service — build_context() is the single entry point that turns a
list of authorized decisions into one formatted context string plus its
decision_count and token_estimate, ready to be handed to the Claude
answering service. Never calls Claude, never summarizes, never re-ranks -
it only formats what PermissionService already authorized.
"""
from __future__ import annotations

import logging
import time

from modules.context.formatter import estimate_tokens, format_context
from modules.context.schemas import AuthorizedDecisionInput, ContextResult

log = logging.getLogger(__name__)


def build_context(authorized_decisions: list[AuthorizedDecisionInput]) -> ContextResult:
    """Format authorized_decisions into one context string.

    Logs decision_count, token_estimate, and context build time (ms) on
    every call.
    """
    start = time.perf_counter()

    context = format_context(authorized_decisions)
    decision_count = len(authorized_decisions)
    token_estimate = estimate_tokens(context)

    elapsed_ms = (time.perf_counter() - start) * 1000
    log.info(
        "Context build: decision_count=%d token_estimate=%d context_build_time_ms=%.3f",
        decision_count,
        token_estimate,
        elapsed_ms,
    )

    return ContextResult(
        context=context, decision_count=decision_count, token_estimate=token_estimate
    )
