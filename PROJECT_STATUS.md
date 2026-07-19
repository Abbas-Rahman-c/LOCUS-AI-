# RAG Evaluation Pipeline — Project Status & Runbook

Last updated: 2026-07-17 (third update — real small-dataset run succeeded with a working key; findings and recommendations written up).

**Read this section first if you're coming back to this after the last delivery.**

---

## Update — 2026-07-17, later same day: dependency pin bug fixed

You ran `scripts/run_small_real_eval.py` on your own machine with a real key loaded correctly (the `ANTHROPIC_API_KEY` naming/`.env` encoding issue got sorted out first). It got further than any previous attempt -- past the auth stage -- and then hit a real bug:

```
TypeError: AsyncMessages.create() got an unexpected keyword argument 'tools'
```

Root cause: `backend/requirements.txt` and `backend/pyproject.toml` pinned `anthropic>=0.25,<0.26` -- an SDK version old enough that `tools` wasn't yet a direct keyword argument on `messages.create()`. Every earlier test attempt died at the 401-auth stage before ever reaching this line, so the bug stayed hidden until a real key actually authenticated far enough to construct the call. **No credits were spent finding this** -- it fails inside the Python SDK locally, before any HTTP request goes out.

Fixed: both files now pin `anthropic>=0.40,<1.0`. Re-verified: all 299 unit tests still pass under the new pin (installed version 0.117.0 in the verification environment). If you already ran `pip install -U anthropic` as a manual workaround, you're fine -- this zip just makes the fix permanent so a fresh `pip install -r requirements.txt` gets it too.

---

## What changed in this delivery

1. **Merged onto your latest upload, not overwritten.** `locusai_2026 2.zip` wasn't just the old project with new keys — it had real independent progress (pgmq client/producer/queues, the event worker, the raw-events store, the Slack webhook handler, `monitoring/health.py`, several new tests). The previous zip I gave you would have clobbered all of that. This delivery starts from your latest upload and adds the retrieval/eval layer on top — `app/main.py` now mounts `health`, `slack`, and `retrieval` routers together; nothing from your ingestion-side work was touched or removed. All 289 tests pass (224 from your side + 65 from mine).

2. **Small-dataset real-run tooling, built exactly as asked.** New: `scripts/run_small_real_eval.py`, `src/tests/fixtures/rag_golden_set_small.json` (5 examples, not 86), and `modules/retrieval/evaluation/known_candidate_pipeline.py`. This makes **10 Anthropic API calls total** (5 synthesis + 5 judge), not 172 — see "Why a *known-candidate* pipeline, not the real one" below for why retrieval itself isn't part of this bounded run.

3. **A real run was attempted and blocked — no credits were spent.** See "The blocker" below.

4. **One real bug fixed along the way:** `scripts/run_rag_eval.py` never called `load_dotenv()`, so outside Docker (whose `env_file:` directive injects `.env` automatically) it would silently never see your API keys when run directly on the host. Fixed — confirmed by re-running it and watching the failure mode change from "missing env var" to "the key itself was rejected," which is the correct behavior.

---

## Real run results (small, credit-bounded)

The key issue and the SDK version bug are both resolved. `scripts/run_small_real_eval.py` ran clean against your real `ANTHROPIC_API_KEY`, making exactly 10 Anthropic calls (5 synthesis + 5 judge) -- no more.

| ID | Category | Groundedness | Correctness | Citation P / R | Notes |
|---|---|---|---|---|---|
| ge-001 | single_hop | 1.0 | 1.0 | 1.0 / 1.0 | Correctly cites the 3-tier decision [D1] |
| ge-002 | paraphrase | 1.0 | 1.0 | 1.0 / 1.0 | Same underlying fact, different phrasing of the question -- answered consistently |
| ge-003 | temporal | 1.0 | 1.0 | 0.5 / 1.0 | Correctly distinguishes the original 5-tier decision [D2] from the superseding one, but cites both D1 and D2 when only D2 was the expected citation -- over-citing, not a factual error |
| ge-004 | multi_hop | 1.0 | 1.0 | 1.0 / 0.5 | Synthesizes correctly across two related decisions but only cites [D1], missing an expected citation of [D2] -- under-citing |
| ge-075 | negative | 1.0 | 1.0 | n/a | Correctly refused to fabricate a vendor -- stated no such decision exists |

Aggregate: Recall@5/@10 = 1.0, Hit Rate@5/@10 = 1.0, MRR = 0.875, negative hit rate = 0.0, groundedness = 1.0, correctness = 1.0, citation precision = 0.875, citation recall = 0.875 (see reliability note below on why the retrieval-shape numbers here -- Recall/Hit Rate/MRR -- aren't meaningful, since this run uses a fixed candidate pool, not live retrieval).

All 5 examples scored a perfect 1.0/1.0 from the Sonnet judge on groundedness and correctness, including the negative example, where the model correctly declined to invent an answer instead of hallucinating a background-check vendor from unrelated candidates in the pool. That refusal behavior is one of the more important things to see working correctly in a decision-intelligence tool. Citation quality wasn't perfect, though: `ge-003` cited one extra decision beyond what was expected (over-citing) and `ge-004` missed an expected citation (under-citing) -- both are real, specific findings that feed directly into the synthesis-prompt recommendation below.

**Scope note, agreed with you directly:** given the key/credit constraints on this delivery, this 5-example, 10-call, known-candidate-pool run is the final real-data evaluation for this round. The retrieval-only metrics in `eval_report_small.json` (Recall@K, MRR, Hit Rate@K) are still not meaningful for this run specifically -- see the next section for why -- but groundedness, correctness, and citation resolution are genuine, real-API results.

## Why a *known-candidate* pipeline, not the real one

Separately from the key issue, I confirmed this sandbox **cannot reach either your Voyage API or your Supabase Postgres**, regardless of credits:

- `api.voyageai.com` → blocked by the sandbox's network allowlist (`403 blocked-by-allowlist` from the proxy)
- Your Supabase pooler host (`aws-0-us-west-1.pooler.supabase.com:6543`) → DNS resolution fails; this sandbox's egress only routes through an HTTP(S) proxy for allowlisted domains, and raw Postgres connections can't go through that at all

`api.anthropic.com` **is** reachable. So the honest, credit-bounded thing to build was a pipeline that's real where it can be and explicit where it can't:

- `retrieve()` returns a **fixed, hand-picked candidate pool** (the `sp-001` pricing-tiers decisions plus every other decision under the same tenant, 11 total) — not real hybrid search. Any Recall@K/MRR/Hit-Rate/latency numbers this produces are **not meaningful** and the code says so in its own docstring.
- `answer()` calls the **real** `synthesizer.synthesize_answer()` — genuine Sonnet/Haiku API call, forced tool-use, real citation mapping.
- Judging calls the **real** `llm_judge.judge_answer()`.

Groundedness and correctness from this run, once the key works, are real signal: "given this candidate pool, does the model write a grounded, correct, well-cited answer." What it can't tell you is whether *hybrid.py* would have found the right candidates in the first place — that still requires your own machine, which has real network access to both Voyage and Supabase. That path is unchanged from the last delivery — see "Setup" below, still accurate.

---

## The 5 examples chosen

| ID | Category | Question |
|---|---|---|
| ge-001 | single_hop | What did we decide about the pricing tiers? |
| ge-002 | paraphrase | How many pricing plans do we offer customers now? |
| ge-003 | temporal | What did we originally decide about pricing tiers, before the current approach? |
| ge-004 | multi_hop | What's the current decision on pricing tiers and how did we get there? |
| ge-075 | negative | Which vendor did we choose for background checks? (correct answer: no such decision exists for this tenant) |

Four share one topic on purpose — it lets the same 11-decision candidate pool test direct lookup, paraphrase robustness, supersession handling, and multi-hop synthesis against the same ground truth, plus one true negative to check the model doesn't fabricate an answer when shown plausible-but-irrelevant candidates (oncall rotation, tech stack, log retention, etc. — all real decisions from other domains in the same tenant).

---

## Findings & recommendations

This section is the "documentation of findings and recommendations for improvement" the task asks for. It draws on two runs: the 86-example mock-pipeline baseline (`eval_report.json`/`.md`, bag-of-words retrieval, exercises the full metric surface at scale) and the 5-example real run above (genuine Sonnet synthesis + judging, small known-candidate pool). Numbers from the mock run describe how the *eval harness* behaves, not production retrieval quality -- the real hybrid pgvector+FTS pipeline has not yet been run against the golden set (needs your machine; see Setup below) -- but they're real numbers from real code, and they surface the same kinds of issues a real run would.

**Mock-pipeline baseline (86 examples):**

| Metric | Value |
|---|---|
| Recall@5 / Recall@10 | 0.932 / 0.932 |
| MRR | 0.852 |
| Hit Rate@5 / Hit Rate@10 | 0.932 / 0.932 |
| Negative-example hit rate (false positives) | 0.417 |
| Citation precision / recall | 0.763 / 0.770 |
| Retrieval latency (mean / p95) | 0.265ms / 0.565ms |

**Issue 1 -- negative hit rate (0.417).** Roughly 42% of the "should return nothing relevant" examples still surfaced a plausible-but-wrong top hit in the mock run. This is the single biggest quality flag in either run. Recommendation: when the real pipeline is evaluated, add a minimum-cosine-similarity floor to the vector leg in `hybrid.py` before a candidate is allowed into RRF fusion, so weakly-related distractors don't get pulled into top-k just because nothing better exists for that tenant. Re-run and diff against baseline with `scripts/diff_eval_reports.py` to confirm this actually lowers the negative hit rate without hurting Recall@K on true positives.

**Issue 2 -- citation precision/recall, confirmed by both runs.** The mock 86-example run showed 0.763/0.770 precision/recall. The real 5-example run confirms this isn't a mock-only artifact: `ge-003` over-cited (cited both D1 and D2 when only D2 was expected) and `ge-004` under-cited (cited only D1, missed an expected D2 citation) -- both on the same pricing-tier supersession chain, where two decisions are topically close enough that the model isn't consistently distinguishing "the decision I'm answering from" versus "a related decision worth mentioning." Recommendation: tighten `modules/ai/prompts/synthesis_prompt.py` with an explicit instruction to cite only decision IDs the answer text directly and specifically draws a claim from, and to treat superseded/related decisions as context rather than citations unless the question is explicitly asking about the history (like `ge-003` was, and correctly should have cited D2 alone).

**Issue 3 -- Hit Rate@5 equals Hit Rate@10 (0.932 both).** In the mock run, going from top-5 to top-10 found nothing extra. If the real hybrid pipeline shows the same flat pattern, `top_k=5` is already sufficient and raising it just adds latency for no recall gain -- a cheap, concrete parameter tuning finding once real data confirms it. If instead a real run shows a *gap* between Hit Rate@5 and @10, that's a signal to either raise `top_k` or improve the RRF fusion so the right answer surfaces higher.

**What the real 5-example run adds:** groundedness and correctness both hit 1.0, and -- more informative than the score itself -- the negative example (`ge-075`) produced a correct refusal rather than a fabricated vendor. That's real evidence the synthesis prompt already handles the "no answer exists" case well; it's the retrieval-precision issues above (negative hit rate, citation quality) that are the actual open risk areas, not synthesis honesty.

**Recommended next steps, in order:**
1. Run `scripts/seed_local_decisions.py` then `scripts/run_rag_eval.py --pipeline real` on your machine (Docker + Postgres/pgvector + Voyage + Anthropic all reachable there) to get real Recall@K/MRR/latency/citation numbers replacing the mock baseline above.
2. Apply the similarity-floor fix in `hybrid.py` for Issue 1, re-run, diff with `diff_eval_reports.py`.
3. Apply the citation-prompt tightening for Issue 2, re-run, diff again.
4. Use the Hit Rate@5-vs-@10 comparison from the real run to decide whether `top_k=5` or `top_k=10` is the better default going forward.

---

## Checklist (updated)

| # | Requirement | Status | Notes |
|---|---|---|---|
| 1 | Golden Evaluation Dataset | ✅ Done | 86-example set, plus new 5-example subset for bounded real runs |
| 2 | Recall@K | ✅ Done (code) | Real numbers still pending a real retrieval run on your machine |
| 3 | MRR | ✅ Done (code) | Same |
| 4 | Retrieval latency | ✅ Done (code) | Same |
| 5 | Overall retrieval accuracy (Hit Rate@K) | ✅ Done (code) | Same |
| 6 | Groundedness | ✅ Done, real numbers | 1.0 across 5 real examples (small credit-bounded run) |
| 7 | Correctness | ✅ Done, real numbers | 1.0 across 5 real examples (small credit-bounded run) |
| 8 | Citation quality | ✅ Done, real + mock numbers | 0.763 / 0.770 precision/recall from mock baseline; real run confirms correct citation resolution on 5 examples |
| 9 | Prompt tuning / retrieval parameter optimization performed | ⚠️ Partial | Initial RRF/synthesis parameters set with documented rationale; iterative tuning against real data still needs your machine (see Findings) |
| 10 | Evaluation scripts | ✅ Done | Now includes the small-dataset script |
| 11 | Metric reports | ✅ Done | Mock 86-example baseline + real 5-example report (`eval_report_small.json`/`.md`), both with real numbers |
| 12 | Documentation of findings | ✅ Done | See Findings & recommendations, above |
| 13 | Recommendations for improvements | ✅ Done | 3 concrete, actionable items in Findings & recommendations |

Everything from the previous `PROJECT_STATUS.md` (full setup steps, troubleshooting, dataset/API/MCP/frontend interaction guides, the tuning loop, file reference) is still accurate and included below unchanged.

---
## Setup — from zero to running

Everything here is PowerShell, run from `C:\Users\tarun\Downloads\locusai_2026\locus_2026`.

### Step 0 — you already did this part

```powershell
cd C:\Users\tarun\Downloads\locusai_2026
Expand-Archive -Path locus_2026.zip -DestinationPath . -Force
```

### Step 1 — Python 3.12 (not 3.14 — see Troubleshooting)

Download the Windows installer from https://www.python.org/downloads/release/python-3120/ , keep "Add to PATH" and "py launcher" checked. Verify:

```powershell
py -0p
```

You should see both 3.14 and 3.12 listed.

### Step 2 — venv + install

```powershell
cd C:\Users\tarun\Downloads\locusai_2026\locus_2026\backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

If that errors on execution policy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

Confirm you see `(.venv)` in the prompt, then:

```powershell
pip install -r requirements.txt -r requirements-dev.txt
```

### Step 3 — run the mock eval (no keys, no DB — proves the harness works)

```powershell
python scripts\run_rag_eval.py --pipeline mock
```

Expect: `Recall@5=0.932 Recall@10=0.932 MRR=0.852`, `Hit Rate@5=0.932 Hit Rate@10=0.932`, `Groundedness=n/a Correctness=n/a` (no Anthropic key yet), writes `eval_report.json`/`eval_report.md` into `backend/`.

### Step 4 — run the unit tests (optional but recommended)

```powershell
pytest src\tests\unit\test_rrf.py src\tests\unit\test_metrics.py src\tests\unit\test_mock_pipeline.py src\tests\unit\test_hybrid.py src\tests\unit\test_resolver.py src\tests\unit\test_synthesizer.py src\tests\unit\test_llm_judge.py src\tests\unit\test_pipeline.py src\tests\unit\test_runner.py -q
```

Expect `65 passed`.

### Step 5 — Docker Desktop

Install from https://www.docker.com/products/docker-desktop/. Verify:

```powershell
docker --version
docker compose version
```

### Step 6 — API keys

```powershell
cd C:\Users\tarun\Downloads\locusai_2026\locus_2026
notepad backend\.env
```

Fill in `VOYAGE_API_KEY` (embeddings) and `ANTHROPIC_API_KEY` (synthesis + judging). `ANTHROPIC_MODEL` is already set to a Sonnet model. `DATABASE_URL` in this file is for your real Supabase instance if you have one — leave it as-is if you're only using the local Docker Postgres, `docker-compose.yml` overrides it automatically for the `backend` container.

### Step 7 — start the local stack

```powershell
docker compose up --build
```

Leave this running in its own terminal. Postgres+pgvector comes up, schema auto-applies from `docker/init-local-schema.sql`, backend API starts at `http://localhost:8000`. Check `http://localhost:8000/docs` in a browser to confirm it's alive.

### Step 8 — seed the local database

New terminal, venv active:

```powershell
cd C:\Users\tarun\Downloads\locusai_2026\locus_2026\backend
.venv\Scripts\Activate.ps1
python scripts\seed_local_decisions.py
```

This loads all 32 scenario packs (the source data the golden set was labeled against) into the local DB and embeds each decision via Voyage. Needs `VOYAGE_API_KEY` set. Prints one line per pack; ends with `Done. N decisions seeded + embedded across 32 scenario packs.`

### Step 9 — run the real eval

```powershell
python scripts\run_rag_eval.py --pipeline real
```

This is the first real number you'll see. Copy `eval_report.json` somewhere as your baseline before you start tuning anything.

---

## Troubleshooting

**`asyncpg` fails to build with `C2198`/`C2223` compiler errors.** You're on Python 3.14. `asyncpg==0.29` is a C extension that doesn't support 3.14's changed CPython internals. Fix: use Python 3.12 (Step 1-2 above). This is unrelated to anything in this codebase — it's a real upstream incompatibility.

**`.venv\Scripts\Activate.ps1` : "running scripts is disabled on this system".** Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first, then activate again. This only affects the current terminal session.

**`python` : "Python was not found; run without arguments to install from the Microsoft Store".** You're not actually inside the activated venv — re-run `.venv\Scripts\Activate.ps1` and confirm `(.venv)` shows in the prompt before running `python` again. Outside a venv, Windows intercepts the bare `python` command with a Store-install stub.

**`pip install` succeeded but nothing seems installed / `python` still broken.** Same root cause as above — if you didn't see `(.venv)` in the prompt when you ran `pip install`, it installed to your global Python instead of the venv.

**`docker compose up` can't reach `db` / backend crashes on startup.** Check `docker compose ps` — the `backend` service has `depends_on: db: condition: service_healthy`, so it waits for Postgres's healthcheck. If `db` never goes healthy, run `docker compose logs db`.

**`seed_local_decisions.py` fails with a Voyage auth error.** `VOYAGE_API_KEY` isn't set or is wrong in `backend/.env`. This script loads `.env` the same way the app does.

**`run_rag_eval.py --pipeline real` returns `groundedness=n/a` / lots of `judge_error`.** `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` missing or invalid — check `eval_report.json`'s `examples[*].judge_error` field for the exact underlying error.

---

## Interacting with the golden dataset directly

The dataset is just JSON + a pydantic loader — you don't need the API running to explore it. From `backend/`, venv active:

```powershell
python
```

```python
import sys
sys.path.insert(0, "src")

from modules.retrieval.evaluation.golden_dataset import load_golden_dataset, load_scenario_packs

dataset = load_golden_dataset("src/tests/fixtures/rag_golden_set_v2.json")
print(len(dataset.examples))              # 86
print(dataset.coverage_report())          # {'single_hop': 34, 'paraphrase': 32, ...}

ex = dataset.examples[0]
print(ex.id, ex.category)                 # ge-001 single_hop
print(ex.question)                        # "What did we decide about the pricing tiers?"
print(ex.tenant_id)                       # 20f0a8ca-afad-5b50-bdd6-c794c0199862
print(ex.expected_decision_ids)           # [UUID('17f4533f-...')]
print(ex.reference_answer)

# The source transcripts + decisions each golden question was labeled against:
packs = load_scenario_packs("src/tests/fixtures/scenario_packs.json")
pack = next(p for p in packs if p.id == "sp-001")
print(pack.raw_transcript)                # the synthetic Slack conversation
for d in pack.decisions:
    print(d.decision_id, d.status, d.distractor_type, d.decision_statement)
```

Field meanings are documented in the docstrings of `golden_dataset.py` itself (`GoldenExample`, `ScenarioPack`, `QuestionCategory`, `DistractorType`) — worth reading directly if you're adding new golden examples. `backend/src/modules/retrieval/evaluation/AUTHORING_GUIDE.md` and `backend/labeling_audit.md` cover how the existing 86 were written and double-labeled.

---

## Talking to the running API

Once `docker compose up` is running (Step 7 above), the backend is at `http://localhost:8000`.

**Health / last eval report:**

```powershell
Invoke-RestMethod -Uri http://localhost:8000/retrieval/status -Method Get
```

Returns `{ database: "ok", last_eval_report: {...} }` — the same JSON `run_rag_eval.py` writes to `eval_report.json`.

**Ask a question** (this is the actual RAG exchange — retrieve, fuse, synthesize, cite):

```powershell
$body = @{
    question  = "What did we decide about the pricing tiers?"
    tenant_id = "20f0a8ca-afad-5b50-bdd6-c794c0199862"
    top_k     = 10
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/retrieval/query -Method Post -Body $body -ContentType "application/json"
```

Response shape:

```json
{
  "answer": "Moved from 5 pricing tiers to a simplified 3-tier structure: Free, Pro, Enterprise. ...",
  "citations": [{ "decision_id": "17f4533f-...", "permalink": "https://example-slack.internal/pricing_tiers/aurora" }],
  "grounded_in": ["17f4533f-...", "..."]
}
```

That `tenant_id` (`20f0a8ca-afad-5b50-bdd6-c794c0199862`) is `sp-001`'s tenant from the seeded scenario packs — swap in any tenant_id from `scenario_packs.json` to ask about a different domain (`oncall`, etc.). This only returns real answers once you've run Step 8 (seeding) — before that, `db` is empty and every query will retrieve nothing.

Interactive docs (try requests from the browser) are auto-generated at `http://localhost:8000/docs`.

---

## Running the small, credit-bounded real eval

Once your Anthropic key works, this needs nothing else -- no Docker, no Postgres, no Voyage:

```powershell
cd C:\Users\tarun\Downloads\locusai_2026\locus_2026\backend
.venv\Scripts\Activate.ps1
python scripts\run_small_real_eval.py
```

Makes exactly 10 real Anthropic calls (5 examples x synthesis+judge) against the fixed 11-decision candidate pool described above. Writes `eval_report_small.json`/`.md`. To use a different/larger small set, copy `src/tests/fixtures/rag_golden_set_small.json`, edit which example IDs it contains (pull them from `rag_golden_set_v2.json`), and pass `--dataset path\to\your\file.json`.

Read `modules/retrieval/evaluation/known_candidate_pipeline.py`'s docstring before trusting any Recall@K/MRR/latency number this produces -- only groundedness/correctness/citation quality are real signal from this script; retrieval itself is a fixed stand-in.

## Using the MCP tools

`modules/mcp/tools/search.py` (`search_decisions`) and `context.py` (`get_decision_context`) wrap the same pipeline for MCP clients (Claude Desktop, Claude Code, etc.), dispatched through `modules/mcp/server.py::handle_tool_call()`. There's no MCP transport (stdio/SSE server process) wired up yet — `server.py` is the dispatch logic an MCP transport layer would sit in front of, not a standalone server you can point a client at today. To call it directly for testing (same venv, same seeded DB):

```python
import asyncio
from uuid import UUID
from modules.mcp.schemas import MCPToolRequest
from modules.mcp.server import handle_tool_call

request = MCPToolRequest(
    tool_name="search_decisions",
    tenant_id=UUID("20f0a8ca-afad-5b50-bdd6-c794c0199862"),
    requesting_client="manual-test",
    params={"query": "pricing tiers", "top_k": 5},
)
response = asyncio.run(handle_tool_call(request))
print(response.result)
```

Every call is logged to `public.mcp_tool_calls` (tool name, params, which decision_ids came back, latency) — that's the audit trail the migration already had a table for.

---

## Using the frontend dashboard

```powershell
cd C:\Users\tarun\Downloads\locusai_2026\locus_2026\frontend
npm install
npm run dev
```

Open the printed URL (usually `http://localhost:5173`), go to `/eval`. It calls `GET /retrieval/status` on the backend, so the backend (Step 7) needs to be running too — it's a read-only view of whatever `eval_report.json` currently says, with a Refresh button. It does not trigger an eval run itself; that's still a CLI step (`run_rag_eval.py`) by design, not a browser action.

---

## The tuning loop — how to finish this

This is what's left after Steps 1-9 above. Not more code — analysis.

1. Save your Step 9 output as a baseline: `cp eval_report.json baseline.json` (or `copy` on Windows).
2. Change one thing:
   - `modules/ai/prompts/synthesis_prompt.py`'s `SYSTEM_PROMPT` wording
   - `modules/retrieval/reranking/rrf.py`'s `DEFAULT_RRF_K`
   - `modules/retrieval/search/hybrid.py`'s `DEFAULT_CANDIDATE_MULTIPLIER` / `MIN_CANDIDATE_POOL`
   - `--top-k` on the CLI
3. Re-run: `python scripts\run_rag_eval.py --pipeline real`
4. Diff: `python scripts\diff_eval_reports.py baseline.json eval_report.json --per-example`
5. Keep the change only if the diff is a net win. Watch `negative_hit_rate` closely — it's the metric most likely to get worse from changes that chase Recall@K.
6. Write up what you found: which `category` (`single_hop`/`paraphrase`/`negative`/`multi_hop`/`temporal`/`ambiguous_entity`) scored worst and why, what each tuning change actually moved, what's still broken. That write-up is items 12/13 from the checklist above — send me the resulting `eval_report.json` and I'll do this pass with you against real numbers.

---

## File reference

| File | Owns |
|---|---|
| `modules/ai/embeddings/provider.py` | `embed_document()` (write path), `embed_query()` (read path) |
| `modules/security/tenant_guard.py` | Tenant pre-filter/RLS-GUC helpers |
| `modules/retrieval/search/hybrid.py` | Vector + keyword legs, concurrent, tenant-scoped |
| `modules/retrieval/reranking/rrf.py` | Merging ranked lists (pure function) |
| `modules/retrieval/citations/resolver.py` | `decision_id → permalink` |
| `modules/ai/prompts/synthesis_prompt.py` | System prompt + forced tool-use schema |
| `modules/retrieval/synthesis/synthesizer.py` | The Sonnet call + citation mapping |
| `modules/retrieval/pipeline.py` | Wires the above behind the `RAGPipeline` Protocol |
| `modules/retrieval/router.py` | `POST /retrieval/query`, `GET /retrieval/status` |
| `modules/mcp/tools/search.py`, `context.py` | MCP tool surface |
| `modules/retrieval/evaluation/mock_pipeline.py` | Zero-I/O Protocol implementation |
| `modules/retrieval/evaluation/runner.py` | Scores any pipeline against the golden set |
| `modules/retrieval/evaluation/metrics.py` | All metric math (pure) |
| `modules/retrieval/evaluation/llm_judge.py` | Sonnet rubric grader |
| `modules/retrieval/evaluation/report.py` | `eval_report.json` / `.md` writers |
| `scripts/run_rag_eval.py` | CLI: `--pipeline mock\|real` (full 86-example set, needs live DB+Voyage for `real`) |
| `scripts/run_small_real_eval.py` | CLI: small (5-example), credit-bounded real Anthropic run, no DB/Voyage needed |
| `modules/retrieval/evaluation/known_candidate_pipeline.py` | Fixed-candidate-pool pipeline backing the small real run |
| `scripts/seed_local_decisions.py` | Loads scenario packs into local DB + embeds them |
| `scripts/diff_eval_reports.py` | The tuning-loop diff tool |
| `docs/rag_pipeline.md` | Architecture deep-dive (this file is the practical runbook; that one's the "why") |
