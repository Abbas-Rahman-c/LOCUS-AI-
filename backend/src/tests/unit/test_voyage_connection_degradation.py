"""
Unit tests verifying Voyage AI connection handling under long-running process simulation.

Verifies:
1. Persistent aiohttp.ClientSession reuse with configured HTTP transport (limit=20, limit_per_host=10, keepalive_timeout=30.0).
2. Simulated long-running server traffic with idle gaps between requests.
3. Automatic session recycling and exponential backoff retry on APIConnectionError / network disconnects.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import voyageai

from modules.ai.embeddings.provider import (
    VoyageEmbeddingError,
    close_voyage_session,
    embed_document,
    embed_query,
    get_voyage_session,
)

DIMENSION = 1024


@pytest_asyncio.fixture(autouse=True)
async def _clean_voyage_env(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "test-voyage-key")
    monkeypatch.setenv("VOYAGE_MODEL", "voyage-4")
    monkeypatch.delenv("VOYAGE_OUTPUT_DIMENSION", raising=False)
    import common.config.voyage_config as voyage_config_module

    voyage_config_module._settings = None
    await close_voyage_session()
    yield
    await close_voyage_session()



def _mock_response(embedding: list[float]):
    return SimpleNamespace(data=[SimpleNamespace(embedding=embedding)])


class TestVoyageConnectionLifecycle:
    pytestmark = pytest.mark.asyncio

    async def test_persistent_session_reused_across_calls(self):
        session1 = get_voyage_session()
        session2 = get_voyage_session()
        assert session1 is session2
        assert not session1.closed
        assert session1.connector.limit == 20
        assert session1.connector.limit_per_host == 10

    async def test_simulated_long_running_server_requests_with_idle_gaps(self):
        """Simulate a long-running process making repeated requests with idle gaps."""
        expected = [0.1] * DIMENSION
        with patch("voyageai.Embedding.acreate", AsyncMock(return_value=_mock_response(expected))) as mock_acreate:
            initial_session = get_voyage_session()

            for i in range(10):
                res_q = await embed_query(f"Search query {i}")
                assert res_q == expected

                # Simulate idle gap between requests (e.g. server waiting for next client call)
                await asyncio.sleep(0.01)

                res_d = await embed_document(f"Document text {i}")
                assert res_d == expected

            # Verify the same session was maintained without connection churn
            final_session = get_voyage_session()
            assert final_session is initial_session
            assert not final_session.closed
            assert mock_acreate.call_count == 20

    async def test_connection_error_recycles_session_and_retries_successfully(self):
        """Simulate a stale socket condition (APIConnectionError) after idle degradation.

        Verifies:
        - The stale initial session is explicitly closed and recycled via close_voyage_session().
        - A fresh, active session is instantiated for the retried attempt.
        - The retried call completes successfully using the fresh session.
        """
        expected = [0.5] * DIMENSION
        mock_acreate = AsyncMock(
            side_effect=[
                voyageai.error.APIConnectionError("Error communicating with Voyage"),
                _mock_response(expected),
            ]
        )
        with patch("voyageai.Embedding.acreate", mock_acreate):
            with patch("modules.ai.embeddings.provider.close_voyage_session", wraps=close_voyage_session) as spy_close:
                initial_session = get_voyage_session()
                assert not initial_session.closed

                # Execute embed_query - attempt 1 encounters APIConnectionError
                result = await embed_query("Query after connection drop")
                assert result == expected

                # 1. Assert close_voyage_session was invoked to recycle the stale session
                spy_close.assert_called()

                # 2. Assert initial session was closed
                assert initial_session.closed

                # 3. Assert get_voyage_session produces a fresh, unclosed session on the retried attempt
                recycled_session = get_voyage_session()
                assert recycled_session is not initial_session
                assert not recycled_session.closed
                assert mock_acreate.call_count == 2

    async def test_rate_limit_429_does_not_recycle_session(self):
        """Simulate an HTTP 429 RateLimitError from Voyage API.

        Verifies:
        - Rate limits trigger retry with backoff.
        - Rate limits do NOT invoke close_voyage_session() or discard the session pool.
        """
        expected = [0.9] * DIMENSION
        mock_acreate = AsyncMock(
            side_effect=[
                voyageai.error.RateLimitError("Rate limit exceeded"),
                _mock_response(expected),
            ]
        )
        with patch("voyageai.Embedding.acreate", mock_acreate):
            with patch("modules.ai.embeddings.provider.close_voyage_session", wraps=close_voyage_session) as spy_close:
                initial_session = get_voyage_session()

                result = await embed_query("Query hitting rate limit")
                assert result == expected

                # Rate limit should NOT trigger session recycling
                spy_close.assert_not_called()
                assert not initial_session.closed
                current_session = get_voyage_session()
                assert current_session is initial_session
                assert mock_acreate.call_count == 2

    async def test_repeated_connection_failures_exhaust_retries(self):
        """Simulate persistent network failure failing after MAX_RETRIES attempts."""
        mock_acreate = AsyncMock(
            side_effect=voyageai.error.APIConnectionError("Error communicating with Voyage")
        )
        with patch("voyageai.Embedding.acreate", mock_acreate):
            with pytest.raises(VoyageEmbeddingError) as exc_info:
                await embed_query("Query during network outage")

            assert "3 attempts" in str(exc_info.value)
            assert mock_acreate.call_count == 3

