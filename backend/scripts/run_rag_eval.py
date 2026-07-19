"""
CLI entry point for the retrieval/RAG evaluation harness.

Usage:
    poetry run python scripts/run_rag_eval.py                       # mock pipeline (no DB/API keys needed)
    poetry run python scripts/run_rag_eval.py --pipeline real       # real hybrid+RRF+Sonnet pipeline
    poetry run python scripts/run_rag_eval.py --dataset src/tests/fixtures/rag_golden_set_v2.json --top-k 10

--pipeline mock (default) uses modules/retrieval/evaluation/mock_pipeline.py
-- crude bag-of-words retrieval + verbatim top-hit synthesis, no I/O.
--pipeline real uses modules/retrieval/pipeline.py -- pgvector cosine +
Postgres full-text search fused with RRF, then a Sonnet call for synthesis
and another for LLM-judge scoring. Requires DATABASE_URL, VOYAGE_API_KEY,
and ANTHROPIC_API_KEY to be set (backend/.env) and a Supabase Postgres
instance with public.decisions / decision_embeddings / decision_sources
populated for the golden set's tenant_ids -- otherwise every example will
come back with PerExampleScore.error set rather than fabricated numbers.

Writes both a machine-readable eval_report.json and a human-readable
eval_report.md to --out-dir (default: repo root). Compare two runs with
scripts/diff_eval_reports.py -- that diff is the prompt-tuning/retrieval-
parameter-optimization loop.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# common/config/anthropic_config.py and voyage_config.py read straight from
# os.environ with no dotenv call of their own (only database_config.py loads
# backend/.env, and only when something imports it) -- outside Docker (whose
# env_file: directive injects .env directly into the container), nothing
# else in this script's import chain would ever load it. Load it explicitly
# here so `--pipeline real` picks up ANTHROPIC_API_KEY/VOYAGE_API_KEY when
# run directly on the host, not just under docker compose.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from modules.retrieval.evaluation.golden_dataset import load_golden_dataset, load_scenario_packs  # noqa: E402
from modules.retrieval.evaluation.mock_pipeline import MockDecisionRecord, MockRAGPipeline  # noqa: E402
from modules.retrieval.evaluation.report import write_json_report, write_markdown_report  # noqa: E402
from modules.retrieval.evaluation.runner import run_evaluation  # noqa: E402
from modules.retrieval.protocol import RAGPipeline  # noqa: E402


def _decision_store_from_scenario_packs(scenario_packs_path: Path) -> list[MockDecisionRecord]:
    """Builds the mock decision store from the generated scenario packs
    (src/tests/fixtures/scenario_packs.json) rather than a hardcoded list --
    this makes the mock run reflect the actual golden dataset, distractors
    and all, including cross-tenant siblings that must never be retrieved
    for the wrong tenant."""
    packs = load_scenario_packs(scenario_packs_path)
    records: list[MockDecisionRecord] = []
    for pack in packs:
        for d in pack.decisions:
            records.append(
                MockDecisionRecord(
                    decision_id=d.decision_id,
                    tenant_id=d.tenant_id,
                    decision_statement=d.decision_statement,
                    rationale=d.rationale,
                    source_permalink=d.source_permalink,
                )
            )
    return records


def _build_pipeline(pipeline_name: str, scenario_packs_path: Path) -> RAGPipeline:
    if pipeline_name == "mock":
        return MockRAGPipeline(decisions=_decision_store_from_scenario_packs(scenario_packs_path))
    if pipeline_name == "real":
        # Imported lazily: modules.retrieval.pipeline pulls in asyncpg/anthropic/
        # voyageai config at import time, which mock-only runs (e.g. CI without
        # secrets) shouldn't need to have configured at all.
        from modules.retrieval.pipeline import RAGPipeline as RealRAGPipeline

        return RealRAGPipeline()
    raise ValueError(f"Unknown --pipeline {pipeline_name!r}, expected 'mock' or 'real'")


async def _main(
    dataset_path: Path, scenario_packs_path: Path, top_k: int, out_dir: Path, pipeline_name: str
) -> None:
    dataset = load_golden_dataset(dataset_path)
    coverage = dataset.coverage_report()
    print(f"Loaded {len(dataset.examples)} golden examples. Category coverage: {coverage}")
    print(f"Pipeline: {pipeline_name}")

    pipeline = _build_pipeline(pipeline_name, scenario_packs_path)
    scores, report = await run_evaluation(dataset, pipeline, top_k=top_k)

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval_report.json"
    md_path = out_dir / "eval_report.md"
    write_json_report(report, scores, json_path)
    write_markdown_report(report, scores, md_path)

    def _fmt(v: float | None) -> str:
        return "n/a" if v is None else f"{v:.3f}"

    print(f"Recall@5={_fmt(report.recall_at_5)}  Recall@10={_fmt(report.recall_at_10)}  MRR={_fmt(report.mrr)}")
    print(f"Hit Rate@5={_fmt(report.hit_rate_at_5)}  Hit Rate@10={_fmt(report.hit_rate_at_10)}  (overall retrieval accuracy)")
    print(f"Negative-example hit rate (false positives): {_fmt(report.negative_hit_rate)}")
    print(f"Groundedness={_fmt(report.groundedness)}  Correctness={_fmt(report.correctness)}")
    print(f"Citation precision={_fmt(report.citation_precision)}  Citation recall={_fmt(report.citation_recall)}")
    print(
        f"Retrieval latency: mean={_fmt(report.mean_retrieval_latency_ms)}ms  "
        f"p95={_fmt(report.p95_retrieval_latency_ms)}ms"
    )
    if report.groundedness is None and report.correctness is None:
        print(
            "(Groundedness/Correctness are n/a: no example was successfully judged -- "
            "check ANTHROPIC_API_KEY/ANTHROPIC_MODEL and eval_report.json[*].judge_error)"
        )
    if report.n_errors:
        print(f"WARNING: {report.n_errors} example(s) errored -- see eval_report.json[*].error")
    print(f"Reports written to {json_path} and {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RAG retrieval evaluation harness.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=SRC_DIR / "tests" / "fixtures" / "rag_golden_set_v2.json",
        help="Path to the golden dataset JSON fixture.",
    )
    parser.add_argument(
        "--scenario-packs",
        type=Path,
        default=SRC_DIR / "tests" / "fixtures" / "scenario_packs.json",
        help="Path to the scenario packs JSON fixture (transcripts + decisions).",
    )
    parser.add_argument("--top-k", type=int, default=10, help="top_k passed to pipeline.retrieve()/answer().")
    parser.add_argument(
        "--pipeline",
        choices=["mock", "real"],
        default="mock",
        help="mock = in-memory bag-of-words pipeline, no credentials needed. "
        "real = hybrid pgvector+FTS retrieval and Sonnet synthesis/judging; needs DATABASE_URL, "
        "VOYAGE_API_KEY, ANTHROPIC_API_KEY and a populated database.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=BACKEND_DIR,
        help="Directory to write eval_report.json / eval_report.md into.",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.dataset, args.scenario_packs, args.top_k, args.out_dir, args.pipeline))


if __name__ == "__main__":
    main()
