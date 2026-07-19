"""
Query Embedding Service — Phase 2 vector retrieval's query-time embedding
step. Wraps modules.ai.embeddings.provider.embed_query() (input_type=
"query") - the same Voyage provider/model as any future document-time
embedding, just asymmetric-search's query side. Never builds its own
Voyage client or duplicates embedding logic.
"""
from __future__ import annotations

from modules.ai.embeddings.provider import embed_query


async def generate_query_embedding(question: str) -> list[float]:
    """Embed a natural-language question for vector similarity search.

    Raises whatever embed_query() raises: VoyageConfigError, ValueError
    (blank question), VoyageEmbeddingError, or VoyageResponseValidationError.
    """
    return await embed_query(question)
