# RAG Evaluation Pipeline — What I Built This Week

This is the wrap-up for this week's work: a real RAG evaluation pipeline for the decision-intelligence backend, replacing what used to be mock implementations. This file is the summary; `README.md` has the "how do I run it" reference, and `PROJECT_STATUS.md` has the full checklist, setup runbook, and detailed findings if you want to go deeper on any of this.

---

## 1. The prompt/retrieval tuning surface: rrf.py, hybrid.py, synthesizer.py, resolver.py

These four files are the actual levers for improving RAG quality, and they're where any future tuning work should happen:

- **`backend/src/modules/retrieval/search/hybrid.py`** — runs pgvector cosine similarity search and Postgres full-text search in parallel (`asyncio.gather`), both scoped to the current tenant. This is the retrieval-parameter tuning surface: similarity thresholds, `top_k` per leg, and FTS query construction all live here.
- **`backend/src/modules/retrieval/reranking/rrf.py`** — Reciprocal Rank Fusion, merging the two hybrid.py result lists into one ranked list (`k=60`, the standard RRF constant from Cormack et al.). The fusion constant `k` and how ties are broken are the tuning knobs here.
- **`backend/src/modules/retrieval/synthesis/synthesizer.py`** — the actual Sonnet call that turns retrieved decisions into a cited, natural-language answer, using forced tool-use so the output is always structured and parseable. The prompt it sends (`backend/src/modules/ai/prompts/synthesis_prompt.py`) is the prompt-tuning surface — this is what needs adjusting based on the citation-quality findings below.
- **`backend/src/modules/retrieval/citations/resolver.py`** — resolves the decision IDs a synthesized answer cites back to their source permalinks (Slack/Gmail/Notion links), so an answer is always traceable back to where the decision actually happened.

Everything downstream (the eval harness, the metrics, the reports) exists to measure whether changes to these four files actually help.

## 2. The evaluation harness

Golden Evaluation Dataset: 86 examples in `backend/src/tests/fixtures/rag_golden_set_v2.json`, covering six question categories (single_hop, multi_hop, temporal, negative, ambiguous_entity, paraphrase), each with expected decision IDs and expected citation IDs.

The harness (`backend/src/modules/retrieval/evaluation/`) computes every metric named in the task spec: Recall@K, MRR, Hit Rate@K ("overall retrieval accuracy"), retrieval latency (mean/p95), groundedness, correctness (both via an LLM-judge — Sonnet scoring against a rubric, not a lexical-overlap heuristic), and citation precision/recall. `scripts/run_rag_eval.py` runs the full set; `scripts/diff_eval_reports.py` diffs two runs — that diff is the tuning loop.

## 3. Reports that show interaction, not just numbers

The original report only printed an aggregate metrics table. That's been extended (`backend/src/modules/retrieval/evaluation/report.py`) to also render a full **"Sample interactions — what worked, what didn't"** section per example: the actual question, the actual generated answer, which decisions got cited, the LLM judge's full rationale, and a one-line verdict (`WORKED` / `ISSUE — <specific reason>` / `FAILED`) computed from the scores rather than eyeballed. See `backend/eval_report_small.md` for a worked example — every one of the 5 real examples has its full transcript, not just a score row.

## 4. Slack/Gmail templates, for dataset accuracy

`backend/src/tests/fixtures/templates/slack_event_template.json` and `gmail_event_template.json` are new. The golden dataset's scenario packs use synthetic `raw_transcript` text and placeholder permalinks (`https://example-slack.internal/...`) — these templates show what a *real* Slack Events API payload and Gmail API message actually look like, how each normalizes into the canonical `EventEnvelope` (matching `modules/ingestion/envelope/schemas.py` field-for-field), and what a real permalink format looks like (`https://<workspace>.slack.com/archives/<channel>/p<ts>` for Slack, `https://mail.google.com/mail/u/0/#inbox/<id>` for Gmail). Each template traces one example all the way from raw provider payload through to the resulting decision record, so future golden-set authoring has something concrete to check itself against instead of an arbitrary guess at what "realistic" source data looks like.

## 5. Real run results — and why they're not the final word

A credit-bounded real run (`scripts/run_small_real_eval.py`, 5 hand-picked examples, exactly 10 real Anthropic calls) produced genuine numbers: groundedness = 1.0, correctness = 1.0, and two concrete citation-quality findings — `ge-003` over-cited (cited two decisions when only one was expected) and `ge-004` under-cited (missed an expected citation). Full transcript in `backend/eval_report_small.md`.

**These results are not fully reliable on their own, and shouldn't be treated as a final quality bar:**

- **The real run is small.** 5 examples against a fixed candidate pool (not live retrieval) — enough to prove the synthesis-and-judging mechanism works correctly (including correctly refusing to fabricate an answer on the negative example), not enough to generalize a quality claim from. It was kept this size specifically to respect Anthropic API cost limits, per instruction.
- **The full 86-example run was optimistic, and for a different reason.** That run (Recall@5 = 0.932, MRR = 0.852, Hit Rate@5 = 0.932, citation precision/recall ≈ 0.76–0.77, negative hit rate = 0.417) covers the whole golden set, but ran against a simplified bag-of-words retrieval stand-in, not the real pgvector + full-text hybrid pipeline. Mock retrieval is a much easier problem than real semantic + lexical search over production embeddings, so those numbers read better than real retrieval would likely score. They confirm the harness is wired correctly end-to-end at scale — they are not evidence of production retrieval quality.
- **Tuning contribution so far:** the retrieval and synthesis parameters were set with real, literature-grounded initial choices rather than arbitrary defaults -- RRF fusion uses the standard `k=60` constant (Cormack et al., the canonical reciprocal-rank-fusion value) instead of naive score concatenation, and the synthesis prompt forces tool-use with explicit citation-formatting instructions rather than free-form generation. What hasn't happened yet is *iterative* tuning -- changing a parameter, re-running against real retrieval, and diffing the result -- because that loop needs real database/Voyage access this environment doesn't have. The next three iterations of that loop are already written up in `PROJECT_STATUS.md` → "Findings & recommendations": a similarity floor in `hybrid.py` for the 41.7% negative-example false-positive rate seen in the mock run, a stricter citation instruction in `synthesis_prompt.py` for the over/under-citing confirmed by the real run, and a `top_k` decision pending real Hit Rate@5-vs-@10 data.

## 6. Flag: the API key is named `ANTHROPIC_API_KEY` in code, not `CLAUDE-HAIKU-KEY`

Worth calling out explicitly since it caused a real blocker this week: the codebase's config (`common/config/anthropic_config.py`) reads the environment variable `ANTHROPIC_API_KEY`. An earlier version of the `.env` had it stored under the name `CLAUDE-HAIKU-KEY` instead — that name is never read by any code path, so the key silently appeared "missing" even when it was present under the wrong name. `CLAUDE-HAIKU-KEY` also isn't a valid environment variable name to begin with (hyphens aren't allowed; `ANTHROPIC_API_KEY` uses underscores, as required). If you're setting this up fresh or handing credentials to someone else on the team, use `ANTHROPIC_API_KEY` — not `CLAUDE-HAIKU-KEY` — in `backend/.env`.

---

## What's in this delivery vs. what needs your own machine

Everything above is real, tested code (299 unit tests passing) and a real, genuine-API-call result on a small scale. What still requires your own machine — Docker, Python 3.12, a Postgres instance with pgvector reachable, and Voyage API access, none of which are reachable from the environment this was built in — is running `scripts/run_rag_eval.py --pipeline real` against the full 86-example set to get real Recall@K/MRR/latency/citation numbers, and then actually applying and diffing the three tuning recommendations above. See `README.md` for exact commands.
