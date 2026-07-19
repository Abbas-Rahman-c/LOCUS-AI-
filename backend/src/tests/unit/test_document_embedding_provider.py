"""
Unit tests for modules.ai.embeddings.provider.embed_document() (ingestion
write path's document-time embedding step).

voyageai.Embedding.acreate is mocked completely via unittest.mock.patch —
no real Voyage API calls are made.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import voyageai

from modules.ai.embeddings.provider import (
    VoyageEmbeddingError,
    VoyageResponseValidationError,
    embed_document,
)

DIMENSION = 1024


@pytest.fixture(autouse=True)
def _voyage_env(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "test-voyage-key")
    monkeypatch.setenv("VOYAGE_MODEL", "voyage-4")
    monkeypatch.delenv("VOYAGE_OUTPUT_DIMENSION", raising=False)
    # get_voyage_config() caches a module-level singleton - clear it so
    # each test observes the env vars set above.
    import common.config.voyage_config as voyage_config_module

    voyage_config_module._settings = None


def _mock_response(embedding: list[float]):
    return SimpleNamespace(data=[SimpleNamespace(embedding=embedding)])


def _patched_acreate(return_value=None, side_effect=None):
    mock = AsyncMock(side_effect=side_effect, return_value=return_value)
    return patch("voyageai.Embedding.acreate", mock), mock


class TestValidResponse:
    pytestmark = pytest.mark.asyncio

    async def test_returns_1024_dimensional_vector(self):
        expected = [0.3] * DIMENSION
        acreate_patch, mock = _patched_acreate(return_value=_mock_response(expected))
        with acreate_patch:
            result = await embed_document("Decision: We chose Stripe for billing.")
        assert result == expected
        assert len(result) == DIMENSION

    async def test_calls_acreate_with_document_input_type_and_configured_model(self):
        acreate_patch, mock = _patched_acreate(return_value=_mock_response([0.0] * DIMENSION))
        with acreate_patch:
            await embed_document("Decision: We chose Stripe for billing.")
        _, kwargs = mock.call_args
        assert kwargs["model"] == "voyage-4"
        assert kwargs["input_type"] == "document"
        assert kwargs["output_dimension"] == DIMENSION
        assert kwargs["input"] == ["Decision: We chose Stripe for billing."]


class TestBlankTextRejected:
    pytestmark = pytest.mark.asyncio

    async def test_empty_string_is_rejected(self):
        with pytest.raises(ValueError):
            await embed_document("")

    async def test_blank_text_never_calls_acreate(self):
        acreate_patch, mock = _patched_acreate(return_value=_mock_response([0.0] * DIMENSION))
        with acreate_patch:
            with pytest.raises(ValueError):
                await embed_document("   ")
        mock.assert_not_called()


class TestWrongVectorLength:
    pytestmark = pytest.mark.asyncio

    async def test_short_vector_is_rejected_before_any_sql_would_run(self):
        """The dimension check happens inside embed_document() itself, so a
        wrong-length vector never even reaches the caller that would bind
        it into an INSERT/UPDATE - see modules.ai.embeddings.service."""
        acreate_patch, mock = _patched_acreate(return_value=_mock_response([0.1] * 512))
        with acreate_patch:
            with pytest.raises(VoyageResponseValidationError):
                await embed_document("Decision: We chose Stripe for billing.")


class TestAPIFailures:
    pytestmark = pytest.mark.asyncio

    async def test_timeout_is_wrapped(self):
        acreate_patch, mock = _patched_acreate(side_effect=voyageai.error.Timeout("timed out"))
        with acreate_patch:
            with pytest.raises(VoyageEmbeddingError):
                await embed_document("Decision: We chose Stripe for billing.")

    async def test_error_message_never_contains_input_text(self):
        secret_text = "Decision: we chose the confidential vendor for payroll."
        acreate_patch, mock = _patched_acreate(side_effect=voyageai.error.Timeout("timed out"))
        with acreate_patch:
            with pytest.raises(VoyageEmbeddingError) as exc_info:
                await embed_document(secret_text)
        assert secret_text not in str(exc_info.value)
