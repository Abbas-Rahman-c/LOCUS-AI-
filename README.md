# LOCUS-AI-
Locus AI is an MCP-native context layer that watches where teams decide - Slack, Gmail, and Notion and continuously turns scattered conversation into a structured, queryable decision register. 

## RAG evaluation pipeline — how to run

Quick-reference for running the RAG evaluation pipeline. For full setup (Docker, Python 3.12, seeding the DB), troubleshooting, and the complete findings writeup, see `PROJECT_STATUS.md` — this file is just the "how do I run it" version.

**Read the reliability note at the bottom before treating any current numbers as final.**

---

## Three ways to run it

### 1. Mock eval — no API keys, no database, instant

Runs the full 86-example golden set against a crude bag-of-words retrieval stand-in. Useful for proving the harness itself works, and for exercising every metric end-to-end with zero cost.

```powershell
cd backend
python scripts\run_rag_eval.py --pipeline mock
```

Writes `eval_report.json` / `eval_report.md` to the `backend/` folder.

### 2. Small real eval — real Anthropic calls, credit-bounded, no database

Runs 5 hand-picked examples against a fixed known-candidate pool (not live retrieval) with real Sonnet synthesis and real Sonnet-judge scoring. Exactly **10 Anthropic API calls total** (5 synthesis + 5 judge) — built specifically to get real groundedness/correctness numbers without running the full 86-example set through the API.

```powershell
cd backend
# .env needs: ANTHROPIC_API_KEY, ANTHROPIC_MODEL
python scripts\run_small_real_eval.py
```

Writes `eval_report_small.json` / `eval_report_small.md`.

### 3. Full real eval — real hybrid retrieval + real API calls, needs a populated database

The actual production pipeline: pgvector cosine search + Postgres full-text search fused with RRF, then real Sonnet synthesis and judging, against all 86 examples. This is the only run that produces real Recall@K, MRR, retrieval latency, and citation-quality numbers.

```powershell
# one-time setup
docker compose up -d
cd backend
python scripts\seed_local_decisions.py   # needs VOYAGE_API_KEY, embeds the golden set's decisions

# the actual eval
# .env needs: DATABASE_URL, VOYAGE_API_KEY, ANTHROPIC_API_KEY, ANTHROPIC_MODEL
python scripts\run_rag_eval.py --pipeline real
```

Writes the same `eval_report.json` / `eval_report.md` as the mock run (real numbers overwrite mock ones — copy the mock report first if you want to keep both).

---

## Comparing two runs (the tuning loop)

After changing a prompt or a retrieval parameter (RRF `k`, `top_k`, a similarity threshold, etc.), re-run whichever eval you changed, then diff against the previous report:

```powershell
python scripts\diff_eval_reports.py path\to\old_eval_report.json path\to\new_eval_report.json
```

This prints per-metric deltas (Recall@K, MRR, Hit Rate@K, groundedness, correctness, citation precision/recall, latency) so you can see exactly what a change did before keeping or reverting it.

---

## Files involved

| Path | What it is |
|---|---|
| `backend/scripts/run_rag_eval.py` | CLI entry point — mock or real pipeline, full 86-example set |
| `backend/scripts/run_small_real_eval.py` | Credit-bounded 5-example real run |
| `backend/scripts/diff_eval_reports.py` | Diffs two `eval_report.json` files — the tuning-loop tool |
| `backend/scripts/seed_local_decisions.py` | Seeds local Postgres + embeds the golden set's decisions via Voyage |
| `backend/src/modules/retrieval/evaluation/` | Harness: `runner.py`, `metrics.py`, `llm_judge.py`, `mock_pipeline.py`, `known_candidate_pipeline.py`, `report.py`, `golden_dataset.py` |
| `backend/src/tests/fixtures/rag_golden_set_v2.json` | Full 86-example golden dataset |
| `backend/src/tests/fixtures/rag_golden_set_small.json` | 5-example subset for the credit-bounded run |
| `backend/eval_report.json` / `.md` | Latest mock (86-example) report |
| `backend/eval_report_small.json` / `.md` | Latest small real (5-example) report |

---

## Reliability note — read before trusting these numbers

Two runs exist right now, and **neither is a final quality bar on its own**:

- **The real 5-example run** (groundedness = 1.0, correctness = 1.0) used genuine Anthropic API calls, so those specific scores are real signal — but 5 examples against a fixed, hand-picked candidate pool (not live retrieval) is too small a sample to generalize from. A perfect score here shows the synthesis-and-judging mechanism works correctly (including correctly refusing to fabricate an answer on the negative example), not that the system is flawless. It was kept this small deliberately, to respect API cost limits.

- **The mock 86-example run** (Recall@5 = 0.932, MRR = 0.852, Hit Rate@5 = 0.932, citation precision/recall ≈ 0.76–0.77) covers the entire golden dataset and every metric, which sounds more convincing — but it runs against a simplified bag-of-words retrieval stand-in, not the real pgvector + full-text hybrid pipeline. Those numbers are optimistic by construction: mock retrieval is a much easier problem than real semantic + lexical search over production embeddings. They confirm the *evaluation harness* is wired correctly end-to-end at scale, not what real retrieval quality looks like.

**Neither has been run yet:** the real hybrid pipeline (`--pipeline real`) against the full 86-example golden set. That's the run that would produce trustworthy Recall@K, MRR, latency, and citation-quality numbers, and it requires a populated Postgres+pgvector database (see option 3 above).

**Tuning contribution so far:** the retrieval and synthesis parameters were set with real, literature-grounded initial choices rather than arbitrary defaults -- RRF fusion uses the standard `k=60` constant (Cormack et al., the canonical reciprocal-rank-fusion value) instead of naive score concatenation, and the synthesis prompt forces tool-use with explicit citation-formatting instructions rather than free-form generation. What hasn't happened yet is *iterative* tuning against real numbers -- `PROJECT_STATUS.md` → "Findings & recommendations" lists three concrete, code-level changes queued up as the next iterations (a similarity floor in `hybrid.py` for the 41.7% negative-example false-positive rate seen in the mock run, a stricter citation instruction in the synthesis prompt, and a `top_k` decision once real Hit Rate@5-vs-@10 data exists). Applying them and re-diffing with `diff_eval_reports.py` against a real `--pipeline real` baseline is the next step.
