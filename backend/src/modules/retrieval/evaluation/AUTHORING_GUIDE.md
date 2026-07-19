# Golden Dataset Authoring Guide

How the retrieval golden dataset is built, and the rules that keep it honest.

## 1. Scenario packs, not standalone Q&A pairs

Every golden question traces back to a **scenario pack**
(`ScenarioPack` in `golden_dataset.py`): a synthetic source transcript
(Slack thread / Gmail chain / Notion page) plus the decision record(s)
extracted from it, plus deliberate distractors.

**Hard rule: write the transcript first, decisions second, question third.**
Never start from a clean `decision_statement` and reverse-engineer a
transcript and question to match it — that ordering leaks the exact
vocabulary the embedding needs to match and makes Recall@K measure nothing
real. Real Slack/Gmail/Notion threads are messy: tangents, people talking
past each other, the actual decision arriving three messages after the
question that prompted it. Transcripts should read that way.

## 2. Distractors are mandatory, not optional flavor

Every scenario pack should include at least one non-answer decision,
tagged with why it's there (`DistractorType`):

| Type | What it tests |
|---|---|
| `superseded` | Does retrieval surface the *current* decision, not an old one it replaced? |
| `rejected_alternative` | Does retrieval avoid citing the option that was considered and turned down? |
| `similar_topic` | Does retrieval discriminate between two real decisions in the same domain? |
| `cross_tenant` | Does retrieval ever leak another tenant's decision into results at all? |

`cross_tenant` distractors are the highest-priority category to get right —
a retrieval bug here is a permission/security bug, not just a quality one.

## 3. Question authoring rules

- Write the question the way a real user would type it into Locus, not the
  way the decision is phrased. Prefer paraphrase over exact terms.
- One scenario pack can back multiple questions (different categories,
  different phrasings) — a real Slack thread gets asked about more than once
  in practice too.
- `negative` questions must be paired against a real candidate pool (a real
  tenant with real scenario packs) where the asked-about topic genuinely
  isn't covered — not an empty pool, which would trivially "pass."

## 4. Double-label + adjudication process

Every `GoldenExample` carries a `LabelingRecord`:

1. **Author** writes the scenario pack + drafts the question — does not
   assign the final relevance label alone.
2. **Labeler A** and **Labeler B** independently review the transcript(s) +
   full candidate decision pool and mark which decisions they'd consider
   relevant, without seeing each other's answer or the author's intent.
3. **Agreement** → locked in, `agreed=True`.
   **Disagreement** → an adjudicator makes the final call and
   `adjudication_note` records *why* — this note is what tells you later
   whether the example itself was genuinely ambiguous (keep it, it's
   valuable) or a labeler was careless (fix or drop it).

### Current status: simulated

This batch was labeled with `simulated=True` — `labeler_a`/`labeler_b` are
two independently-implemented scan functions (keyword/entity match vs.
topic/paraphrase match) run over each scenario's transcript and candidate
pool, standing in for two humans until real reviewers are available. Where
they agree, the label is treated as settled. Where they don't, the
disagreement and adjudication reasoning is recorded exactly as it would be
for real labelers — nothing is hidden, `simulated=True` is just a flag that
this batch's agreement rate isn't a real inter-rater reliability signal yet.

**Before relying on this dataset to gate a retrieval or prompt change**,
replace at least the disagreement cases (`agreed=False`) with real human
review, and ideally re-review a random sample of the `agreed=True` cases too
— simulated agreement can still be systematically wrong in the same
direction on both "labelers" since they're both authored by the same
process.

## 5. Coverage targets

Not just question `category` — also track:
- **source**: slack / gmail / notion
- **domain**: free-text topic tag (pricing, oncall, vendor, etc.)
- **distractor_type** present in the candidate pool
- **tenant**: multiple tenants exist specifically to exercise `cross_tenant`
  distractors

Run `GoldenDataset.coverage_report()` before adding a large batch — if
`negative` or `cross_tenant` cases are thin relative to `single_hop`, that's
the gap to fill next, not more single-hop variants.

## 6. Versioning

Treat additions to the golden set like a code change: review before merging,
and prefer adding examples that came from an actual production failure once
real retrieval exists — those are more valuable than more imagined variety.
