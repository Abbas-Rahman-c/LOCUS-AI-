"""
Vector Retrieval Service — orchestrates question -> query embedding ->
tenant-scoped vector similarity search -> top-K matches.

No permission-scope filtering, context building, or Claude answering
happen here - this is retrieval only, computed entirely inside the
authenticated tenant. See modules/search/service.py for the full
orchestration this feeds into.
"""
from __future__ import annotations

import uuid

import asyncpg

from modules.retrieval.vector.query_embedding import generate_query_embedding
from modules.retrieval.vector.repository import search_similar_decisions
from modules.retrieval.vector.schemas import DEFAULT_TOP_K, RetrievalMatch


async def search(
    pool: asyncpg.Pool,
    tenant_id: uuid.UUID | str,
    question: str,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[list[RetrievalMatch], int]:
    """Run question -> query embedding -> tenant-scoped vector search -> top-K.

    Returns (matches, embedding_dimension). Raises whatever
    generate_query_embedding() / search_similar_decisions() raise:
    VoyageConfigError, ValueError (blank question, bad top_k/embedding),
    VoyageEmbeddingError, VoyageResponseValidationError, or an
    asyncpg.PostgresError from the DB.
    """
    embedding = await generate_query_embedding(question)
    matches = await search_similar_decisions(pool, tenant_id, embedding, top_k)
    return matches, len(embedding)
