"""Unit tests for modules.retrieval.citations.resolver."""
from __future__ import annotations

from uuid import uuid4

import pytest

from modules.retrieval.citations import resolver
from tests.fixtures.fakes import FakeConnection, FakePool

TENANT = uuid4()


@pytest.mark.asyncio
async def test_resolve_permalinks_returns_permalink_for_known_decision():
    d1, d2 = uuid4(), uuid4()
    conn = FakeConnection(
        fetch_by_marker={
            "decision_sources": [{"decision_id": d1, "permalink": "https://example.internal/d1"}]
        }
    )
    result = await resolver.resolve_permalinks([d1, d2], TENANT, pool=FakePool(conn))
    assert result[d1] == "https://example.internal/d1"
    assert result[d2] is None  # present as a key even though unresolved


@pytest.mark.asyncio
async def test_resolve_permalinks_empty_input_short_circuits_without_query():
    conn = FakeConnection()
    result = await resolver.resolve_permalinks([], TENANT, pool=FakePool(conn))
    assert result == {}
    assert conn.calls == []


@pytest.mark.asyncio
async def test_resolve_permalinks_requires_tenant_id():
    with pytest.raises(ValueError):
        await resolver.resolve_permalinks([uuid4()], None, pool=FakePool(FakeConnection()))


@pytest.mark.asyncio
async def test_resolve_citations_preserves_input_order():
    d1, d2 = uuid4(), uuid4()
    conn = FakeConnection(
        fetch_by_marker={
            "decision_sources": [{"decision_id": d2, "permalink": "https://example.internal/d2"}]
        }
    )
    citations = await resolver.resolve_citations([d1, d2], TENANT, pool=FakePool(conn))
    assert [c.decision_id for c in citations] == [d1, d2]
    assert citations[0].permalink is None
    assert citations[1].permalink == "https://example.internal/d2"
