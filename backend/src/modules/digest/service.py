"""
Digest Service — generate_team_pulse() is the single entry point for the
weekly "Team Pulse" and "Your Week in Decisions" digests.

This service does NOT add any new retrieval, embedding, or Claude-calling
logic. It entirely reuses the existing search pipeline
(modules.search.service.search()) — the only difference is:

  1. The *question* is a fixed, time-windowed prompt instead of a live user
     query ("Summarize the key decisions made in the past 7 days").
  2. The *response shape* is DigestResponse instead of SearchResponse — a
     lighter, digest-oriented projection of the same underlying data.
  3. top_k is raised (default 25) so the digest captures more of the week's
     decisions than a typical single-question search.

scope="personal" generates "Your Week in Decisions" (individual view).
scope="team" generates the "Team Pulse" (team-wide view).

Both scopes use the same pipeline — permission_scopes passed in from the
router (already resolved server-side from the authenticated TenantContext)
naturally controls what decisions each caller can see.

tenant_id must already be authenticated before this function is called —
it is never validated here. That is the router's responsibility.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import asyncpg

from modules.context.service import build_context
from modules.context.schemas import AuthorizedDecisionInput
from modules.digest.schemas import DigestItem, DigestMetadata, DigestResponse
from modules.permissions.service import filter_accessible_decisions
from modules.retrieval.vector.service import search as vector_search
from modules.answering.service import generate_answer

log = logging.getLogger(__name__)

# Digest retrieves more decisions than a point query to cover the full week.
_DIGEST_TOP_K = 25

_PERSONAL_QUESTION = (
    "Summarize the key decisions I was involved in or that affected my work "
    "over the past 7 days. Group by theme if helpful."
)

_TEAM_QUESTION = (
    "What were the most important decisions made by the team this week? "
    "Summarize them clearly, grouped by theme if helpful."
)


def _period_string() -> str:
    """Return an ISO 8601 date-range string for the past 7 days."""
    now = datetime.now(tz=timezone.utc)
    week_ago = now - timedelta(days=7)
    return f"{week_ago.date().isoformat()}/{now.date().isoformat()}"


async def generate_team_pulse(
    pool: asyncpg.Pool,
    tenant_id: uuid.UUID | str,
    permission_scopes: list[str],
    scope: Literal["personal", "team"] = "team",
) -> DigestResponse:
    """Generate the weekly Team Pulse or personal digest.

    Reuses the full search pipeline (vector retrieval → permission filter →
    context builder → Claude answer) with a fixed time-windowed question.

    tenant_id must already be authenticated (from TenantContext) — this
    function never validates it. That trust boundary is the router's job.
    """
    question = _PERSONAL_QUESTION if scope == "personal" else _TEAM_QUESTION

    # Step 1: vector retrieval (same as /search, just higher top_k)
    matches, _ = await vector_search(pool, tenant_id, question, _DIGEST_TOP_K)

    # Step 2: permission filter (Layer 2 — same as /search)
    authorized = filter_accessible_decisions(permission_scopes, matches)

    # Step 3: build context string from authorized decisions
    context_inputs = [
        AuthorizedDecisionInput(
            decision_statement=m.decision_statement,
            rationale=m.rationale,
            alternatives=list(m.alternatives_considered),
            confidence=m.confidence,
            created_at=m.created_at.isoformat() if m.created_at else None,
            decision_type=m.decision_type,
            owner=m.owner,
        )
        for m in authorized
    ]
    context_result = build_context(context_inputs)

    # Step 4: generate Claude summary
    answer_result = await generate_answer(question, context_result.context)

    # Step 5: project authorized decisions into DigestItem shape
    items = [
        DigestItem(
            decision_statement=m.decision_statement,
            rationale=m.rationale,
            confidence=m.confidence,
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in authorized
    ]

    log.info(
        "Digest generated: scope=%s retrieved=%d authorized=%d model=%s latency_ms=%.3f",
        scope,
        len(matches),
        len(authorized),
        answer_result.model,
        answer_result.latency_ms,
    )

    return DigestResponse(
        scope=scope,
        period=_period_string(),
        summary=answer_result.answer,
        items=items,
        metadata=DigestMetadata(
            model=answer_result.model,
            latency_ms=answer_result.latency_ms,
            decision_count=context_result.decision_count,
            token_estimate=context_result.token_estimate,
        ),
    )
