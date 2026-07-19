"""
RAGPipeline Protocol -- the seam between the eval harness
(modules.retrieval.evaluation.runner) and whatever actually answers a
question, mock or real.

This is intentionally the *entire* interface runner.py is allowed to know
about. As long as both modules.retrieval.pipeline.RAGPipeline (real,
DB + Sonnet backed) and modules.retrieval.evaluation.mock_pipeline.MockRAGPipeline
(in-memory, no I/O) satisfy this Protocol, swapping one for the other in
scripts/run_rag_eval.py is a one-line change -- runner.py and metrics.py
never import either implementation directly, only this Protocol.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from modules.retrieval.schemas import RetrievalResult, SynthesizedAnswer


@runtime_checkable
class RAGPipeline(Protocol):
    """Structural type both MockRAGPipeline and the real RAGPipeline implement."""

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 10) -> RetrievalResult:
        """Return the tenant-scoped, RRF-fused candidate list for `query`."""
        ...

    async def answer(self, query: str, tenant_id: UUID, top_k: int = 10) -> SynthesizedAnswer:
        """Retrieve, then synthesize a grounded, cited answer.

        Implementations should internally call something equivalent to
        retrieve() rather than duplicating retrieval logic, but the
        Protocol only constrains the two public entry points the eval
        harness actually calls: retrieve() for Recall@K/MRR/negative hit
        rate, answer() for groundedness/correctness.
        """
        ...
