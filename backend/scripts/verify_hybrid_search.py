"""
One-shot, bounded verification of semantic_only / keyword_only / hybrid_rrf
retrieval on a representative subset of the Stage 2 queries. Calls the
retrieval functions directly (not the HTTP endpoint, not Claude) - this
only re-verifies retrieval/fusion correctness, which Stage 2 already
covered end-to-end for the unchanged semantic path, so no Claude calls are
needed here at all.

Cost-minimizing design: the query embedding is generated exactly ONCE per
question (not once per mode) and reused for both the semantic-only result
and the vector half of the hybrid result - exactly 1 Voyage call per
question, 0 Claude calls, 0 HTTP requests.

Usage:
    cd backend
    PYTHONPATH=src .venv/bin/python scripts/verify_hybrid_search.py
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import asyncpg
from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

from common.config.database_config import get_app_database_config
from modules.ai.embeddings.provider import embed_query
from modules.retrieval.reranking.rrf import DEFAULT_RRF_K, fuse_rrf
from modules.retrieval.vector.keyword_repository import search_decisions_keyword
from modules.retrieval.vector.repository import search_similar_decisions

TENANT_ID = "13bcd0fa-1ed9-4634-93c7-278ba97ec658"
TOP_K = 5

# A representative subset of the approved Stage 2 query set, spanning
# exact_keyword, semantic_paraphrase, rationale, and both multi_decision
# cases (including multi-01, the one genuine Stage 2 retrieval miss).
SAMPLE_QUERIES = [
    ("kw-01", "Why did we choose Stripe instead of Paddle?",
     ["91b4aa2f-a02c-44c2-be89-10053f9d32f4"]),
    ("kw-02", "Why are we migrating the job queue from Redis Streams to pgmq?",
     ["f8aeac83-5ec7-4a05-914c-112bc85cf668"]),
    ("para-03", "What analytics tooling change did the data team make?",
     ["3c766c71-448d-44fb-8b30-6b6d7960ada0"]),
    ("rat-03", "Why did we migrate off self-hosted Snowplow?",
     ["3c766c71-448d-44fb-8b30-6b6d7960ada0"]),
    ("multi-01", "What infrastructure decisions have we made recently?",
     ["a992a87e-e964-4dec-822a-c2fda9269ba9", "8473d874-f519-4e86-be71-12c26a5ba2d7",
      "47a5d5f4-7cc2-4a5b-81e2-b968f03279cf"]),
    ("multi-03", "What blockers are currently affecting different teams?",
     ["6b1ee81d-793c-4525-9b5a-b5cc3f84ec69", "b006a28d-723d-4319-b84b-a60485059772",
      "6d741b8c-3a55-499b-ad8b-f1f8c0d847e1", "facdb6a7-2bde-4324-b365-114c81f1c8c8",
      "a9b1bbbf-6ff0-4c91-b718-89a307273e52"]),
]


def _ids(matches) -> list[str]:
    return [str(m.decision_id)[:8] for m in matches]


async def main() -> None:
    config = get_app_database_config()
    pool = await asyncpg.create_pool(dsn=config.dsn, min_size=1, max_size=5, statement_cache_size=0)

    print(f"Verifying {len(SAMPLE_QUERIES)} queries across semantic_only / keyword_only / hybrid_rrf\n")
    voyage_calls = 0

    try:
        for test_id, question, expected in SAMPLE_QUERIES:
            expected_short = [e[:8] for e in expected]
            print(f"=== {test_id}: {question}")
            print(f"    expected: {expected_short}")

            t0 = time.perf_counter()
            embedding = await embed_query(question)
            voyage_calls += 1
            embed_ms = (time.perf_counter() - t0) * 1000

            t1 = time.perf_counter()
            vector_matches = await search_similar_decisions(pool, TENANT_ID, embedding, TOP_K)
            vector_ms = (time.perf_counter() - t1) * 1000
            print(f"  semantic_only  ({vector_ms:6.1f}ms retrieval + {embed_ms:6.1f}ms embed): {_ids(vector_matches)}")

            t2 = time.perf_counter()
            keyword_matches = await search_decisions_keyword(pool, TENANT_ID, question, TOP_K)
            keyword_ms = (time.perf_counter() - t2) * 1000
            print(f"  keyword_only   ({keyword_ms:6.1f}ms, 0 external calls):        {_ids(keyword_matches)}")

            t3 = time.perf_counter()
            fused = fuse_rrf(vector_matches, keyword_matches, top_k=TOP_K, k=DEFAULT_RRF_K)
            fuse_ms = (time.perf_counter() - t3) * 1000
            print(f"  hybrid_rrf     (+{fuse_ms:.2f}ms fusion, total ~{vector_ms+keyword_ms+fuse_ms:6.1f}ms): "
                  f"{_ids(fused)}")
            print(f"    hybrid RRF scores: {[round(m.rrf_score, 4) for m in fused]}")

            hit_semantic = sum(1 for e in expected for m in vector_matches if str(m.decision_id) == e)
            hit_keyword = sum(1 for e in expected for m in keyword_matches if str(m.decision_id) == e)
            hit_hybrid = sum(1 for e in expected for m in fused if str(m.decision_id) == e)
            print(f"    expected-hits -> semantic:{hit_semantic}/{len(expected)}  "
                  f"keyword:{hit_keyword}/{len(expected)}  hybrid:{hit_hybrid}/{len(expected)}")
            print()
    finally:
        await pool.close()

    print(f"DONE. Total Voyage calls made: {voyage_calls}. Total Claude calls made: 0. Total HTTP requests: 0.")


if __name__ == "__main__":
    asyncio.run(main())
