"""
Voyage AI embedding provider — embed_document() wraps voyageai's async HTTP
resource for document-time embeddings (input_type="document").

SDK note (voyageai==0.2.4, pinned by pyproject.toml's `voyageai = "^0.2"`):
the high-level voyageai.AsyncClient.embed() wrapper is async-native
(aiohttp-backed under the hood, not a sync client wrapped in a thread) but
its signature only exposes texts/model/input_type/truncation — no
output_dimension. output_dimension is nonetheless a real Voyage API request
parameter, so this module calls the lower-level voyageai.Embedding.acreate()
resource directly (the same call AsyncClient.embed() makes internally) and
adds output_dimension to the kwargs; api_resources/api_resource.py forwards
arbitrary **params straight into the POST body. Because the transport is
already async (aiohttp), no asyncio.to_thread is needed.

Query-time embeddings (input_type="query") are handled by embed_query()
below, used by modules.retrieval.search.hybrid for the vector leg of
hybrid search.
"""
from __future__ import annotations

import logging

import voyageai
from voyageai.error import VoyageError

from common.config.voyage_config import VoyageConfigError, get_voyage_config

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30.0
_DOCUMENT_INPUT_TYPE = "document"


class VoyageEmbeddingError(Exception):
    """The Voyage API call itself failed (auth, rate limit, timeout, connection)."""


class VoyageResponseValidationError(Exception):
    """The Voyage API returned a response that doesn't match the expected shape."""


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

    try:
        response = await voyageai.Embedding.acreate(
            input=[text],
            model=config.model,
            input_type=_DOCUMENT_INPUT_TYPE,
            output_dimension=config.output_dimension,
            truncation=True,
            api_key=config.api_key,
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

    if not isinstance(embedding, list) or len(embedding) != config.output_dimension:
        got = len(embedding) if isinstance(embedding, list) else type(embedding).__name__
        raise VoyageResponseValidationError(
            f"Voyage returned a vector of length/type {got!r}, expected {config.output_dimension} floats"
        )

    try:
        return [float(x) for x in embedding]
    except (TypeError, ValueError) as exc:
        raise VoyageResponseValidationError(
            f"Voyage returned a non-numeric embedding value: {type(exc).__name__}"
        ) from exc


_QUERY_INPUT_TYPE = "query"


async def embed_query(text: str) -> list[float]:
    """Embed a user's retrieval question with input_type="query".

    Voyage AI's asymmetric models (voyage-4 family) require query-time text
    to be embedded with input_type="query" rather than "document" -- using
    the wrong input_type doesn't error, it just silently degrades cosine
    similarity against document embeddings written by embed_document(). This
    is the "query-time embeddings ... out of scope here" placeholder this
    module's docstring pointed at; hybrid.py's vector leg calls this, never
    embed_document(), for the same reason process_embedding_job() never
    calls this for decision text.

    Raises the same error types as embed_document(): VoyageConfigError,
    ValueError (blank text), VoyageEmbeddingError, VoyageResponseValidationError.
    """
    if not text or not text.strip():
        raise ValueError("embed_query() text must not be blank")

    config = get_voyage_config()

    try:
        response = await voyageai.Embedding.acreate(
            input=[text],
            model=config.model,
            input_type=_QUERY_INPUT_TYPE,
            output_dimension=config.output_dimension,
            truncation=True,
            api_key=config.api_key,
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

    if not isinstance(embedding, list) or len(embedding) != config.output_dimension:
        got = len(embedding) if isinstance(embedding, list) else type(embedding).__name__
        raise VoyageResponseValidationError(
            f"Voyage returned a vector of length/type {got!r}, expected {config.output_dimension} floats"
        )

    try:
        return [float(x) for x in embedding]
    except (TypeError, ValueError) as exc:
        raise VoyageResponseValidationError(
            f"Voyage returned a non-numeric embedding value: {type(exc).__name__}"
        ) from exc
