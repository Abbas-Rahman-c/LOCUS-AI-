"""
Voyage AI embedding provider — query-time embeddings for Phase 2 retrieval.

embed_query() wraps voyageai's async HTTP resource with input_type="query",
the asymmetric-search counterpart to document-time embedding (input_type=
"document"). Document-time embedding (embeds decision summaries once at
write-time) belongs to the ingestion pipeline and is deferred Phase 1 work,
ported separately once Phase 2 retrieval/search is working cleanly.
"""
from __future__ import annotations

import logging

import voyageai
from voyageai.error import VoyageError

from common.config.voyage_config import VoyageConfigError, get_voyage_config

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30.0
_QUERY_INPUT_TYPE = "query"


class VoyageEmbeddingError(Exception):
    """The Voyage API call itself failed (auth, rate limit, timeout, connection)."""


class VoyageResponseValidationError(Exception):
    """The Voyage API returned a response that doesn't match the expected shape."""


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

    try:
        response = await voyageai.Embedding.acreate(
            input=[text],
            model=config.voyage_model,
            input_type=_QUERY_INPUT_TYPE,
            output_dimension=config.voyage_output_dimension,
            truncation=True,
            api_key=config.voyage_api_key,
            request_timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except VoyageError as exc:
        raise VoyageEmbeddingError(f"Voyage embedding request failed: {type(exc).__name__}") from exc
    except VoyageConfigError:
        raise
    except Exception as exc:
        raise VoyageEmbeddingError(
            f"Voyage embedding request failed unexpectedly: {type(exc).__name__}"
        ) from exc

    try:
        embedding = response.data[0].embedding
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise VoyageResponseValidationError(
            f"Malformed Voyage embedding response: {type(exc).__name__}"
        ) from exc

    if not isinstance(embedding, list) or len(embedding) != config.voyage_output_dimension:
        got = len(embedding) if isinstance(embedding, list) else type(embedding).__name__
        raise VoyageResponseValidationError(
            f"Voyage returned a vector of length/type {got!r}, expected "
            f"{config.voyage_output_dimension} floats"
        )

    try:
        return [float(x) for x in embedding]
    except (TypeError, ValueError) as exc:
        raise VoyageResponseValidationError(
            f"Voyage returned a non-numeric embedding value: {type(exc).__name__}"
        ) from exc
