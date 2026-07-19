# RAG retrieval pipeline

**Read this before changing anything under `backend/src/modules/retrieval/`.**

## What actually happens on a query

```
question ──> embed_query() (Voyage, input_type="query")
                 │
                 ├──> vector leg:   public.decisions JOIN public.decision_embeddings
                 │                  ORDER BY embedding <=> query_embedding   (hybrid.py)
                 │
                 └──> keyword leg:  public.decisions
                                    WHERE to_tsvector(...) @@ plainto_tsquery(question) (hybrid.py)
                 │
                 ▼
        reciprocal_rank_fusion([vector, keyword])           (rrf.py)
                 │
                 ▼
        top_k RankedDecision list
                 │
                 ▼
        synthesize_answer() -- forced tool-use Sonnet call   (synthesizer.py)
                 │
                 ▼
        resolve_citations() -- decision_id -> permalink      (resolver.py)
                 │
                 ▼
        SynthesizedAnswer { answer_text, citations, grounded_in }
```

`modules/retrieval/pipeline.py`'s `RAGPipeline` class wires all of this
behind two methods, `retrieve()` and `answer()`, defined as a
`typing.Protocol` in `modules/retrieval/protocol.py`. Everything under
`modules/retrieval/evaluation/` (the harness) and `modules/mcp/tools/`
(the MCP tool surface) only ever imports that Protocol -- never
`RAGPipeline` or `MockRAGPipeline` by name -- so swapping the pipeline
implementation never requires touching the eval harness or the MCP tools.

Every query is tenant-scoped twice: an explicit `WHERE tenant_id = $1` in
every SQL statement (`modules/security/tenant_guard.py`'s "pre-filter"
layer), plus the RLS GUC (`set_tenant_context()`) as defense in depth. See
`tenant_guard.py`'s docstring for why both layers matter -- retrieval is
the one place in this codebase where a missing tenant filter becomes
cross-tenant data disclosure inside an AI-generated answer, not a 404.

## Running the eval harness

```bash
cd backend

# Mock pipeline: crude bag-of-words retrieval, no DB/API keys needed.
# This is a smoke test for the harness itself, not a retrieval-quality signal.
poetry run python scripts/run_rag_eval.py --pipeline mock

# Real pipeline: needs DATABASE_URL, VOYAGE_API_KEY, ANTHROPIC_API_KEY,
# ANTHROPIC_MODEL set (backend/.env), and a database with public.decisions /
# decision_embeddings / decision_sources populated for the golden set's
# tenant_ids (src/tests/fixtures/scenario_packs.json has the exact
# decisions + transcripts the golden set was labeled against -- seed those).
poetry run python scripts/run_rag_eval.py --pipeline real
```

Both write `eval_report.json` and `eval_report.md` to the backend repo
root (`--out-dir` to change that). `eval_report.json`'s `report` block has `recall_at_5`, `recall_at_10`,
`hit_rate_at_5`, `hit_rate_at_10`, `mrr`, `negative_hit_rate`,
`groundedness`, `correctness`, `citation_precision`, `citation_recall`,
`mean_retrieval_latency_ms`, `p95_retrieval_latency_ms` -- any of these can
be `null` (not `0.0`) when
nothing was successfully scored for that metric (e.g. `groundedness`/
`correctness` are `null` if `ANTHROPIC_API_KEY` isn't set -- check
`eval_report.json.examples[*].judge_error`).

`hit_rate_at_5`/`hit_rate_at_10` are "overall retrieval accuracy": a
binary pass/fail per example (was *any* expected decision retrieved in the
top K?), distinct from `recall_at_k`'s partial credit -- a `multi_hop`
example with 2 expected decisions and only 1 retrieved scores
`recall_at_10=0.5` but `hit_at_10=True` (not a total miss).

`citation_precision`/`citation_recall` are scored against
`GoldenExample.expected_citation_ids` -- a distinct signal from
`recall_at_k`. `recall_at_k` asks whether the right decision was
*retrieved* anywhere in the candidate pool; citation quality asks whether
the *synthesized answer* actually cited it. A pipeline can retrieve the
right decision and still cite the wrong one (or nothing) -- that failure
mode only shows up here, not in Recall@K.

`mean_retrieval_latency_ms`/`p95_retrieval_latency_ms` time
`RAGPipeline.retrieve()` only (embed_query + both search legs + RRF
fusion) -- not synthesis or judging, which are dominated by Sonnet API
latency and would drown out the retrieval-specific signal these two
numbers exist to isolate.

## Why the mock numbers are highs, not a target

`modules/retrieval/evaluation/mock_pipeline.py`'s `MockRAGPipeline` scores
retrieval with plain bag-of-words Jaccard overlap between the question and
each candidate's `decision_statement`/`rationale` text -- no embeddings, no
Postgres ranking, no RRF fusion of two independently imperfect signals, no
distractor suppression. It exists so the eval harness (and CI) can run with
zero credentials, not as a retrieval-quality baseline. Expect the real
pipeline's `Recall@K`/`MRR` to come in *below* the mock's, and
`negative_hit_rate` to often come in *above* it (real embeddings surface
semantically-similar distractors -- `superseded`, `rejected_alternative`,
`similar_topic` in `scenario_packs.json` -- that bag-of-words overlap
mostly misses). That gap is expected, not a bug.

## The tuning loop

This is the only loop this codebase supports for improving retrieval
quality now that `hybrid.py`/`rrf.py`/`synthesizer.py`/`resolver.py` are
real: prompt tuning and retrieval-parameter tuning, scored against the
same 86-example golden set every time.

```bash
# 1. Establish a baseline.
poetry run python scripts/run_rag_eval.py --pipeline real --out-dir baseline

# 2. Change ONE thing:
#    - modules/ai/prompts/synthesis_prompt.py's SYSTEM_PROMPT wording
#    - modules/retrieval/reranking/rrf.py's DEFAULT_RRF_K
#    - modules/retrieval/search/hybrid.py's DEFAULT_CANDIDATE_MULTIPLIER / MIN_CANDIDATE_POOL
#    - --top-k on the CLI itself

# 3. Re-run.
poetry run python scripts/run_rag_eval.py --pipeline real

# 4. Diff.
poetry run python scripts/diff_eval_reports.py baseline/eval_report.json eval_report.json --per-example
```

Keep the change only if the diff is a net win -- watch `negative_hit_rate`
especially closely; it's the metric most likely to get worse from changes
that chase `Recall@K` (a lower candidate-pool multiplier or looser RRF `k`
can pull in more true positives *and* more distractors at once).

## What each file owns

| File | Owns |
|---|---|
| `modules/ai/embeddings/provider.py` | `embed_document()` (write path), `embed_query()` (read path) -- different Voyage `input_type` |
| `modules/security/tenant_guard.py` | The tenant pre-filter/RLS-GUC helpers every retrieval query calls |
| `modules/retrieval/search/hybrid.py` | Vector leg + keyword leg, run concurrently, tenant-scoped |
| `modules/retrieval/reranking/rrf.py` | Merging any number of ranked lists into one (pure function, no I/O) |
| `modules/retrieval/citations/resolver.py` | `decision_id -> permalink`, only for the final top_k |
| `modules/ai/prompts/synthesis_prompt.py` | The system prompt + forced tool-use schema Sonnet answers against |
| `modules/retrieval/synthesis/synthesizer.py` | The actual Sonnet call + label-to-UUID citation mapping |
| `modules/retrieval/pipeline.py` | Wires the above behind the `RAGPipeline` Protocol |
| `modules/retrieval/router.py` | `POST /retrieval/query`, `GET /retrieval/status` |
| `modules/mcp/tools/search.py`, `context.py` | MCP tool surface over the same pipeline |
| `modules/retrieval/evaluation/mock_pipeline.py` | Zero-I/O Protocol implementation for fast/CI runs |
| `modules/retrieval/evaluation/runner.py` | Scores any `RAGPipeline` against a `GoldenDataset` |
| `modules/retrieval/evaluation/metrics.py` | Recall@K / MRR / negative-hit-rate math (pure) |
| `modules/retrieval/evaluation/llm_judge.py` | Sonnet rubric grader for groundedness/correctness |
| `modules/retrieval/evaluation/report.py` | `eval_report.json` / `eval_report.md` writers |
| `scripts/run_rag_eval.py` | CLI: `--pipeline mock\|real` |
| `scripts/diff_eval_reports.py` | The tuning-loop diff tool |
