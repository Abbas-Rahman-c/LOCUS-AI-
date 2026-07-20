"""
Unit tests for modules.permissions.service.filter_accessible_decisions().

Exercises the aggregate behavior (mixed accessible/rejected decisions,
counts, logging) on top of the pure predicate already covered by
tests/unit/test_permission_repository.py. All fixtures share one tenant_id
- tenant isolation is RLS's job, not this module's.
"""
from __future__ import annotations

import logging
from uuid import uuid4

from modules.permissions.service import filter_accessible_decisions
from modules.retrieval.vector.schemas import RetrievalMatch

TENANT = uuid4()


def _decision(permission_scope: list[str] | None = None) -> RetrievalMatch:
    return RetrievalMatch(
        decision_id=uuid4(),
        decision_statement="We chose Stripe for PCI-compliant billing.",
        similarity_score=0.9,
        confidence=0.9,
        tenant_id=TENANT,
        permission_scope=permission_scope if permission_scope is not None else ["team:billing"],
    )


class TestFiltering:
    def test_keeps_only_accessible_decisions(self):
        accessible = _decision(permission_scope=["team:billing"])
        wrong_scope = _decision(permission_scope=["team:sales"])

        result = filter_accessible_decisions(["team:billing"], [accessible, wrong_scope])

        assert result == [accessible]

    def test_empty_input_returns_empty_list(self):
        assert filter_accessible_decisions(["team:billing"], []) == []

    def test_all_accessible_preserves_order(self):
        first = _decision(permission_scope=["team:billing"])
        second = _decision(permission_scope=["team:engineering"])

        result = filter_accessible_decisions(["team:billing", "team:engineering"], [first, second])

        assert result == [first, second]

    def test_none_accessible_returns_empty_list(self):
        decisions = [
            _decision(permission_scope=["team:sales"]),
            _decision(permission_scope=["team:marketing"]),
        ]
        assert filter_accessible_decisions(["team:billing"], decisions) == []


class TestWorkspaceWideFailsClosedForOrdinaryMembers:
    """The realistic /search scenario: an ordinary member's server-derived
    permission_scopes is [] (modules.permissions.scope_resolver - no
    repository evidence supports granting anyone a non-empty scope).
    Workspace-wide (empty-scope) decisions must still surface; any
    genuinely scoped decision must be excluded - proving Layer 2 fails
    closed rather than falling back to trusting anything client-supplied."""

    def test_workspace_wide_decisions_survive_with_no_caller_scopes(self):
        workspace_wide = _decision(permission_scope=[])
        scoped = _decision(permission_scope=["team:billing"])

        result = filter_accessible_decisions([], [workspace_wide, scoped])

        assert result == [workspace_wide]


class TestLogging:
    def test_logs_retrieved_authorized_rejected_and_timing(self, caplog):
        decisions = [
            _decision(permission_scope=["team:billing"]),
            _decision(permission_scope=["team:sales"]),
        ]

        with caplog.at_level(logging.INFO, logger="modules.permissions.service"):
            filter_accessible_decisions(["team:billing"], decisions)

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "retrieved=2" in message
        assert "authorized=1" in message
        assert "rejected=1" in message
        assert "filtering_time_ms=" in message
