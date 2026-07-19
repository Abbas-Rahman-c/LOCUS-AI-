"""
Unit tests for modules.retrieval.vector.service.search().

generate_query_embedding() and search_similar_decisions() are mocked
completely via modules.retrieval.vector.service's imported names — no real
Voyage API call and no real database connection are made.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from modules.retrieval.vector.schemas import RetrievalMatch
from modules.retrieval.vector.service import search

EMBEDDING = [0.001 * i for i in range(1024)]

pytestmark = pytest.mark.asyncio


def _match(tenant_id) -> RetrievalMatch:
    return RetrievalMatch(
        decision_id=uuid.uuid4(),
        decision_statement="We chose Stripe for PCI-compliant billing.",
        similarity_score=0.87,
        confidence=0.9,
        tenant_id=tenant_id,
        permission_scope=["team:billing"],
    )


class TestSearchFlow:
    async def test_embeds_question_then_searches_within_tenant(self):
        tenant_id = uuid.uuid4()
        matches = [_match(tenant_id)]
        embed_mock = AsyncMock(return_value=EMBEDDING)
        repo_mock = AsyncMock(return_value=matches)
        pool = object()

        with (
            patch("modules.retrieval.vector.service.generate_query_embedding", embed_mock),
            patch("modules.retrieval.vector.service.search_similar_decisions", repo_mock),
        ):
            result_matches, dimension = await search(
                pool, tenant_id, "Why did we choose Stripe?", top_k=5
            )

        embed_mock.assert_awaited_once_with("Why did we choose Stripe?")
        repo_mock.assert_awaited_once_with(pool, tenant_id, EMBEDDING, 5)
        assert result_matches == matches
        assert dimension == len(EMBEDDING)

    async def test_propagates_embedding_errors(self):
        embed_mock = AsyncMock(side_effect=ValueError("blank question"))
        repo_mock = AsyncMock()

        with (
            patch("modules.retrieval.vector.service.generate_query_embedding", embed_mock),
            patch("modules.retrieval.vector.service.search_similar_decisions", repo_mock),
        ):
            with pytest.raises(ValueError):
                await search(object(), uuid.uuid4(), "", top_k=5)
        repo_mock.assert_not_called()

    async def test_empty_matches_still_returns_dimension(self):
        embed_mock = AsyncMock(return_value=EMBEDDING)
        repo_mock = AsyncMock(return_value=[])

        with (
            patch("modules.retrieval.vector.service.generate_query_embedding", embed_mock),
            patch("modules.retrieval.vector.service.search_similar_decisions", repo_mock),
        ):
            result_matches, dimension = await search(
                object(), uuid.uuid4(), "Why did we choose Stripe?"
            )
        assert result_matches == []
        assert dimension == len(EMBEDDING)
