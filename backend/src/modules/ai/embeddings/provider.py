"""
Voyage AI embedding provider — query-time and document-time embeddings.

embed_query() wraps voyageai's async HTTP resource with input_type="query";
embed_document() does the same with input_type="document". Voyage's
asymmetric search model expects queries and documents to be embedded with
their respective input_type - never the same call for both - so the two
functions are kept explicit and separate rather than parameterized, to
make it impossible for a caller to accidentally use the wrong one.

embed_query() backs Phase 2 retrieval (modules.retrieval.vector.service).
embed_document() backs the ingestion write path (modules.ai.embeddings.
service), embedding a decision's searchable text once at persistence time.
"""
from __future__ import annotations

import logging

import asyncio
import logging
from typing import Any

import aiohttp
import voyageai
from voyageai.error import VoyageError

from common.config.voyage_config import VoyageConfigError, get_voyage_config

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30.0
_QUERY_INPUT_TYPE = "query"
_DOCUMENT_INPUT_TYPE = "document"

MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 0.5

_session: aiohttp.ClientSession | None = None


class VoyageEmbeddingError(Exception):
    """The Voyage API call itself failed (auth, rate limit, timeout, connection)."""


class VoyageResponseValidationError(Exception):
    """The Voyage API returned a response that doesn't match the expected shape."""


def get_voyage_session() -> aiohttp.ClientSession:
    """Get or create a managed, persistent aiohttp.ClientSession for Voyage AI calls.

    Configures HTTP transport with explicit keepalive, connection pool limits,
    and proactive cleanup of closed connections to prevent connection degradation
    over long-running server lifetimes.
    """
    global _session
    if _session is None or _session.closed or _session._loop.is_closed():
        connector = aiohttp.TCPConnector(
            limit=20,
            limit_per_host=10,
            keepalive_timeout=30.0,
            enable_cleanup_closed=True,
        )
        _session = aiohttp.ClientSession(connector=connector)
        voyageai.aiosession.set(_session)
    return _session


async def close_voyage_session() -> None:
    """Close the persistent Voyage aiohttp.ClientSession if initialized."""
    global _session
    if _session is not None and not _session.closed:
        try:
            await _session.close()
        except Exception as exc:
            log.warning("Error closing Voyage HTTP session: %s", exc)
        finally:
            _session = None
            voyageai.aiosession.set(None)


async def _execute_embedding_request(text: str, input_type: str) -> Any:
    """Execute a Voyage embedding request with session pooling and retry-on-connection-failure."""
    config = get_voyage_config()
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        session = get_voyage_session()
        try:
            response = await voyageai.Embedding.acreate(
                input=[text],
                model=config.voyage_model,
                input_type=input_type,
                output_dimension=config.voyage_output_dimension,
                truncation=True,
                api_key=config.voyage_api_key,
                request_timeout=REQUEST_TIMEOUT_SECONDS,
            )
            return response
        except VoyageConfigError:
            raise
        except voyageai.error.RateLimitError as exc:
            # HTTP 429 Rate Limit: do NOT recycle session (session recycling does not fix rate limits).
            # Log specific warning and retry with longer backoff.
            last_exc = exc
            log.warning(
                "Voyage API rate limit (429) hit on attempt %d/%d: %s. Backing off...",
                attempt,
                MAX_RETRIES,
                exc,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2.0 * (2 ** (attempt - 1)))
        except (
            voyageai.error.APIConnectionError,
            voyageai.error.Timeout,
            aiohttp.ClientError,
            asyncio.TimeoutError,
        ) as exc:
            status_code = (
                getattr(exc, "http_status", None)
                or getattr(exc, "status", None)
                or getattr(exc, "code", None)
            )
            if status_code == 429:
                last_exc = exc
                log.warning(
                    "Voyage API rate limit (429) status on attempt %d/%d: %s. Backing off...",
                    attempt,
                    MAX_RETRIES,
                    exc,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2.0 * (2 ** (attempt - 1)))
                continue

            last_exc = exc
            log.warning(
                "Voyage API connection failure (attempt %d/%d): %s. Recycling session...",
                attempt,
                MAX_RETRIES,
                type(exc).__name__,
            )
            await close_voyage_session()
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF_FACTOR * (2 ** (attempt - 1)))
        except VoyageError as exc:
            raise VoyageEmbeddingError(f"Voyage embedding request failed: {type(exc).__name__}") from exc
        except Exception as exc:
            raise VoyageEmbeddingError(
                f"Voyage embedding request failed unexpectedly: {type(exc).__name__}"
            ) from exc

    raise VoyageEmbeddingError(
        f"Voyage embedding request failed after {MAX_RETRIES} attempts: {type(last_exc).__name__}"
    ) from last_exc



def _parse_and_validate_embedding(response: Any, expected_dimension: int) -> list[float]:
    """Validate and extract the float vector from Voyage's raw response."""
    try:
        embedding = response.data[0].embedding
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise VoyageResponseValidationError(
            f"Malformed Voyage embedding response: {type(exc).__name__}"
        ) from exc

    if not isinstance(embedding, list) or len(embedding) != expected_dimension:
        got = len(embedding) if isinstance(embedding, list) else type(embedding).__name__
        raise VoyageResponseValidationError(
            f"Voyage returned a vector of length/type {got!r}, expected "
            f"{expected_dimension} floats"
        )

    try:
        return [float(x) for x in embedding]
    except (TypeError, ValueError) as exc:
        raise VoyageResponseValidationError(
            f"Voyage returned a non-numeric embedding value: {type(exc).__name__}"
        ) from exc


async def embed_query(text: str) -> list[float]:
    """Embed a natural-language search query with input_type="query".

    Raises VoyageConfigError if Voyage configuration is missing/invalid,
    ValueError if text is blank, VoyageEmbeddingError if the Voyage API call
    fails, or VoyageResponseValidationError if the response shape or vector
    length is wrong. Never logs the input text or the API key.
    """
    if not text or not text.strip():
        raise ValueError("embed_query() text must not be blank")

    config = get_voyage_config()
    response = await _execute_embedding_request(text, _QUERY_INPUT_TYPE)
    return _parse_and_validate_embedding(response, config.voyage_output_dimension)


async def embed_document(text: str) -> list[float]:
    """Embed one decision's searchable text with input_type="document".

    Raises VoyageConfigError if Voyage configuration is missing/invalid,
    ValueError if text is blank, VoyageEmbeddingError if the Voyage API call
    fails, or VoyageResponseValidationError if the response shape or vector
    length is wrong. Never logs the input text or the API key.
    """
    if not text or not text.strip():
        raise ValueError("embed_document() text must not be blank")

    config = get_voyage_config()
    response = await _execute_embedding_request(text, _DOCUMENT_INPUT_TYPE)
    return _parse_and_validate_embedding(response, config.voyage_output_dimension)

