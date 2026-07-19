# RAG Evaluation Report -- KnownCandidateRAGPipeline

Generated: 2026-07-17T23:14:22.279712+00:00
Examples: 5 (errors: 0)  |  top_k: 10

## Aggregate metrics

| Metric | Value |
|---|---|
| Recall@5 | 1.000 |
| Recall@10 | 1.000 |
| Hit Rate@5 (retrieval accuracy) | 1.000 |
| Hit Rate@10 (retrieval accuracy) | 1.000 |
| MRR | 0.875 |
| Negative hit rate (false positives) | 0.000 |
| Groundedness (LLM judge) | 1.000 |
| Correctness (LLM judge) | 1.000 |
| Citation precision | 0.875 |
| Citation recall | 0.875 |
| Mean retrieval latency (ms) | 0.000 |
| P95 retrieval latency (ms) | 0.000 |

## Category coverage

| Category | Count |
|---|---|
| multi_hop | 1 |
| negative | 1 |
| paraphrase | 1 |
| single_hop | 1 |
| temporal | 1 |

## Per-example detail

| ID | Category | Recall@10 | RR | Neg FP | Groundedness | Correctness | Cite P | Cite R | Latency (ms) | Error |
|---|---|---|---|---|---|---|---|---|---|---|
| ge-001 | single_hop | 1.000 | 1.000 | - | 1.000 | 1.000 | 1.000 | 1.000 | 0.0 |  |
| ge-002 | paraphrase | 1.000 | 1.000 | - | 1.000 | 1.000 | 1.000 | 1.000 | 0.0 |  |
| ge-003 | temporal | 1.000 | 0.500 | - | 1.000 | 1.000 | 0.500 | 1.000 | 0.0 |  |
| ge-004 | multi_hop | 1.000 | 1.000 | - | 1.000 | 1.000 | 1.000 | 0.500 | 0.0 |  |
| ge-075 | negative | - | - | False | 1.000 | 1.000 | - | - | 0.0 |  |

## Sample interactions -- what worked, what didn't

Full question/answer/judge-rationale transcript for every example in this run, in place of raw numbers alone.

### ge-001 [single_hop] -- WORKED -- retrieved, grounded, correct, cited cleanly

**Question:** What did we decide about the pricing tiers?

**Answer:** The team decided to move from 5 pricing tiers to a simplified 3-tier structure consisting of Free, Pro, and Enterprise [D1]. This decision was driven by data showing that 7 of the last 12 lost deals cited confusion about the original tier structure, with the expectation that simplification would speed up the sales cycle.

**Cited:** 17f4533f-7a50-5081-aa78-bd2838b681bc

**Judge rationale:** groundedness: Every factual claim in the generated answer is directly supported by the retrieved decision record D1. The answer states: (1) the team moved from 5 tiers to 3 tiers—matches D1; (2) the new structure is Free, Pro, Enterprise—matches D1; (3) 7 of the last 12 lost deals cited tier confusion—directly quoted from D1's rationale; (4) the expectation is that simplification would speed the sales cycle—directly from D1's rationale. There are no unsupported or overstated claims. | correctness: The generated answer conveys the same substantive meaning as the reference answer. Both communicate the core decision (move to 3-tier structure: Free, Pro, Enterprise), the problem it addresses (7 of 12 lost deals cited tier confusion), and the intended benefit (speed the sales cycle). The generated answer adds minor elaboration ("data showing," "with the expectation that") but does not contradict or misstate the reference's substance. The citation to D1 is accurate.

### ge-002 [paraphrase] -- WORKED -- retrieved, grounded, correct, cited cleanly

**Question:** How many pricing plans do we offer customers now?

**Answer:** You now offer 3 pricing plans [D1]: Free, Pro, and Enterprise. This reflects a move from the earlier 5-tier structure to a simplified model aimed at reducing tier confusion in the sales cycle.

**Cited:** 17f4533f-7a50-5081-aa78-bd2838b681bc

**Judge rationale:** groundedness: Every factual claim in the generated answer is directly supported by D1. The answer states: (1) "3 pricing plans" - supported by D1's "3-tier structure"; (2) "Free, Pro, and Enterprise" - exactly matches D1's stated tiers; (3) "move from the earlier 5-tier structure" - supported by D1's "Move from 5 pricing tiers"; (4) "simplified model aimed at reducing tier confusion in the sales cycle" - supported by D1's rationale mentioning "tier confusion" and "simplifying should speed the sales cycle." No unsupported claims are present. | correctness: The generated answer conveys the same substantive meaning as the reference answer. Both identify the current pricing structure as a 3-tier model (Free, Pro, Enterprise) resulting from a move away from the previous 5-tier structure. The generated answer goes slightly further by explaining the rationale (reducing tier confusion), but this is supplementary context that does not contradict or misstate the reference's substance. The core claim—that the company now offers 3 pricing plans with the specific tier names—is fully aligned with the reference.

### ge-003 [temporal] -- ISSUE -- over-cited (precision 0.50)

**Question:** What did we originally decide about pricing tiers, before the current approach?

**Answer:** Originally, you decided to launch with 5 pricing tiers: Free, Starter, Growth, Business, and Enterprise [D2]. This decision was later superseded by the current approach of moving to a simplified 3-tier structure (Free, Pro, Enterprise) after discovering that tier confusion was cited in 7 of the last 12 lost deals [D1].

**Cited:** 4b8d1cb9-f88d-5dc7-be65-bc677ff0de09, 17f4533f-7a50-5081-aa78-bd2838b681bc

**Judge rationale:** groundedness: Every factual claim in the generated answer is directly supported by the retrieved decision records. The answer cites D2 for the original 5-tier structure (Free, Starter, Growth, Business, Enterprise) and D1 for the current 3-tier approach, with the rationale about tier confusion in 7 of 12 lost deals. All details match the exact content of these decision records with no unsupported additions. | correctness: The generated answer fully matches the reference answer's substance. The reference answer states "Launch with 5 pricing tiers: Free, Starter, Growth, Business, Enterprise," and the generated answer correctly conveys this exact information from D2. The generated answer also appropriately contextualizes this by explaining how it was superseded, which provides helpful context without contradicting or misrepresenting the original decision.

### ge-004 [multi_hop] -- ISSUE -- under-cited (recall 0.50)

**Question:** What's the current decision on pricing tiers and how did we get there?

**Answer:** The current decision on pricing tiers is to move from 5 tiers to a simplified 3-tier structure: Free, Pro, and Enterprise [D1]. This was decided after the team observed that 7 of the last 12 lost deals cited tier confusion, so the simplification is expected to speed up the sales cycle [D1].

**Cited:** 17f4533f-7a50-5081-aa78-bd2838b681bc

**Judge rationale:** groundedness: Every factual claim in the generated answer is directly supported by the retrieved decision records. The answer states: (1) the current decision is to move from 5 tiers to a 3-tier structure (Free, Pro, Enterprise) – directly from D1; (2) this was decided – D1 has status=decided; (3) 7 of the last 12 lost deals cited tier confusion – exact quote from D1's rationale; (4) the simplification is expected to speed the sales cycle – exact quote from D1's rationale. The answer also correctly cites D1 as the source. No unsupported claims or inferences beyond what D1 provides are present. | correctness: The generated answer conveys the same substantive meaning as the reference answer. Both identify the current decision (3-tier structure: Free, Pro, Enterprise) and how the team got there (previous 5-tier structure). The generated answer adds the rationale (tier confusion in lost deals, sales cycle speedup), which is consistent with and reinforces the reference answer's substance without contradicting it. The generated answer fully addresses the question "What's the current decision on pricing tiers and how did we get there?"

### ge-075 [negative] -- WORKED -- correctly declined to answer (true negative)

**Question:** Which vendor did we choose for background checks?

**Answer:** There is no recorded decision about which vendor to choose for background checks in the provided records.

**Judge rationale:** groundedness: The generated answer states that there is no recorded decision about background check vendors. I have reviewed all 10 decision records (D1–D10) and none of them mention background checks, vendors for background checks, or any related HR/recruiting vendor decision. The answer makes no unsupported claims—it correctly identifies the absence of relevant information in the retrieved records. | correctness: The generated answer matches the reference answer in substance. Both correctly state that no relevant decision exists on this topic. The generated answer properly conveys that the decision records do not contain information about background check vendors, which aligns precisely with the reference answer's statement that "No recorded decision exists on this topic for this tenant."
