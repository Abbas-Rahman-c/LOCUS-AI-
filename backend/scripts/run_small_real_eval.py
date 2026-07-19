"""
CLI entry point for a real, credit-bounded Anthropic-backed eval run over a
small hand-picked example set -- for environments that can reach
api.anthropic.com but cannot reach Postgres or api.voyageai.com (see
modules/retrieval/evaluation/known_candidate_pipeline.py's docstring for
exactly what is and isn't real about this).

This is deliberately NOT scripts/run_rag_eval.py --pipeline real: that
script needs a live Postgres+pgvector instance and Voyage embeddings.
This one needs only ANTHROPIC_API_KEY/ANTHROPIC_MODEL, and only ever makes
2 Anthropic calls per example (one synthesis call, one judge call) -- for
the default 5-example set, that's 10 calls total, not 172 (86 * 2).

Usage:
    poetry run python scripts/run_small_real_eval.py
    poetry run python scripts/run_small_real_eval.py --dataset src/tests/fixtures/rag_golden_set_small.json
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

load_dotenv(BACKEND_DIR / ".env")

from modules.retrieval.evaluation.golden_dataset import load_golden_dataset, load_scenario_packs  # noqa: E402
from modules.retrieval.evaluation.known_candidate_pipeline import KnownCandidateRAGPipeline  # noqa: E402
from modules.retrieval.evaluation.report import write_json_report, write_markdown_report  # noqa: E402
from modules.retrieval.evaluation.runner import run_evaluation  # noqa: E402


def _candidate_decisions_for_dataset(dataset, scenario_packs_path: Path):
    """Builds the known-candidate pool from exactly the scenario packs the
    small dataset's examples reference (plus every other pack sharing the
    same tenant_id, so negative examples have realistic distractors to
    correctly decline rather than an empty, trivially-negative pool)."""
    referenced_pack_ids = {pid for ex in dataset.examples for pid in ex.scenario_pack_ids}
    tenant_ids = {ex.tenant_id for ex in dataset.examples}

    packs = load_scenario_packs(scenario_packs_path)
    selected = [p for p in packs if p.id in referenced_pack_ids or p.tenant_id in tenant_ids]

    decisions = []
    for pack in selected:
        decisions.extend(pack.decisions)
    return decisions, [p.id for p in selected]


async def _main(dataset_path: Path, scenario_packs_path: Path, top_k: int, out_dir: Path) -> None:
    dataset = load_golden_dataset(dataset_path)
    print(f"Loaded {len(dataset.examples)} example(s) from {dataset_path.name}")
    for ex in dataset.examples:
        print(f"  {ex.id} [{ex.category.value}]: {ex.question}")

    decisions, pack_ids = _candidate_decisions_for_dataset(dataset, scenario_packs_path)
    print(f"Known-candidate pool: {len(decisions)} decisions from scenario packs {pack_ids}")

    n_calls = len(dataset.examples) * 2
    print(
        f"\nThis will make {n_calls} real Anthropic API call(s) "
        f"({len(dataset.examples)} synthesis + {len(dataset.examples)} judge), no Voyage/Postgres calls.\n"
    )

    pipeline = KnownCandidateRAGPipeline(decisions=decisions)
    scores, report = await run_evaluation(dataset, pipeline, top_k=top_k, concurrency=2)

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval_report_small.json"
    md_path = out_dir / "eval_report_small.md"
    write_json_report(report, scores, json_path)
    write_markdown_report(report, scores, md_path)

    print("\n--- Results (retrieval metrics below are NOT meaningful -- see") 
    print("    known_candidate_pipeline.py docstring. Groundedness/correctness ARE real.) ---")
    for s in scores:
        print(f"  {s.example_id} [{s.category}]: groundedness={s.groundedness} correctness={s.correctness}")
        print(f"    answer: {s.answer_text[:200]}")
        if s.error:
            print(f"    ERROR: {s.error}")
        if s.judge_error:
            print(f"    JUDGE ERROR: {s.judge_error}")

    print(f"\nGroundedness={report.groundedness}  Correctness={report.correctness}")
    print(f"Reports written to {json_path} and {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small, credit-bounded real Anthropic eval.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=SRC_DIR / "tests" / "fixtures" / "rag_golden_set_small.json",
    )
    parser.add_argument(
        "--scenario-packs",
        type=Path,
        default=SRC_DIR / "tests" / "fixtures" / "scenario_packs.json",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--out-dir", type=Path, default=BACKEND_DIR)
    args = parser.parse_args()
    asyncio.run(_main(args.dataset, args.scenario_packs, args.top_k, args.out_dir))


if __name__ == "__main__":
    main()
