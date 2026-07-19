# RAG Evaluation Report -- MockRAGPipeline

Generated: 2026-07-17T21:57:06.231528+00:00
Examples: 86 (errors: 0)  |  top_k: 10

## Aggregate metrics

| Metric | Value |
|---|---|
| Recall@5 | 0.932 |
| Recall@10 | 0.932 |
| Hit Rate@5 (retrieval accuracy) | 0.932 |
| Hit Rate@10 (retrieval accuracy) | 0.932 |
| MRR | 0.852 |
| Negative hit rate (false positives) | 0.417 |
| Groundedness (LLM judge) | - |
| Correctness (LLM judge) | - |
| Citation precision | 0.763 |
| Citation recall | 0.770 |
| Mean retrieval latency (ms) | 0.259 |
| P95 retrieval latency (ms) | 0.587 |

## Category coverage

| Category | Count |
|---|---|
| ambiguous_entity | 4 |
| multi_hop | 2 |
| negative | 12 |
| paraphrase | 32 |
| single_hop | 34 |
| temporal | 2 |

## Per-example detail

| ID | Category | Recall@10 | RR | Neg FP | Groundedness | Correctness | Cite P | Cite R | Latency (ms) | Error |
|---|---|---|---|---|---|---|---|---|---|---|
| ge-001 | single_hop | 1.000 | 0.500 | - | - | - | 0.000 | 0.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-002 | paraphrase | 1.000 | 0.333 | - | - | - | 0.000 | 0.000 | 0.1 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-003 | temporal | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-004 | multi_hop | 1.000 | 1.000 | - | - | - | 1.000 | 0.500 | 0.1 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-005 | single_hop | 1.000 | 0.500 | - | - | - | 0.000 | 0.000 | 0.1 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-006 | paraphrase | 1.000 | 0.500 | - | - | - | 0.000 | 0.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-007 | temporal | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-008 | multi_hop | 1.000 | 1.000 | - | - | - | 1.000 | 0.500 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-009 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-010 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-011 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 1.8 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-012 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-013 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-014 | paraphrase | 1.000 | 0.500 | - | - | - | 0.000 | 0.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-015 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.1 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-016 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-017 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-018 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-019 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-020 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.5 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-021 | single_hop | 1.000 | 0.500 | - | - | - | 0.000 | 0.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-022 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-023 | ambiguous_entity | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-024 | single_hop | 1.000 | 0.500 | - | - | - | 0.000 | 0.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-025 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-026 | ambiguous_entity | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-027 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-028 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-029 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-030 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-031 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-032 | paraphrase | 0.000 | 0.000 | - | - | - | - | 0.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-033 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-034 | paraphrase | 0.000 | 0.000 | - | - | - | - | 0.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-035 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-036 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-037 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-038 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.4 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-039 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.6 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-040 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.4 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-041 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-042 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-043 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-044 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.1 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-045 | single_hop | 1.000 | 0.500 | - | - | - | 0.000 | 0.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-046 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-047 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-048 | paraphrase | 1.000 | 0.250 | - | - | - | 0.000 | 0.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-049 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.1 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-050 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-051 | single_hop | 1.000 | 0.500 | - | - | - | 0.000 | 0.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-052 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-053 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-054 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-055 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-056 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.8 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-057 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-058 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-059 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-060 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-061 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-062 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-063 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.1 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-064 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-065 | single_hop | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-066 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-067 | single_hop | 0.000 | 0.000 | - | - | - | 0.000 | 0.000 | 0.4 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-068 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-069 | single_hop | 0.000 | 0.000 | - | - | - | 0.000 | 0.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-070 | paraphrase | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-071 | ambiguous_entity | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-072 | ambiguous_entity | 1.000 | 1.000 | - | - | - | 1.000 | 1.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-073 | single_hop | 0.000 | 0.000 | - | - | - | - | 0.000 | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-074 | single_hop | 1.000 | 0.500 | - | - | - | 0.000 | 0.000 | 0.8 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-075 | negative | - | - | False | - | - | - | - | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-076 | negative | - | - | True | - | - | 0.000 | - | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-077 | negative | - | - | False | - | - | - | - | 0.1 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-078 | negative | - | - | True | - | - | 0.000 | - | 0.3 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-079 | negative | - | - | True | - | - | 0.000 | - | 0.8 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-080 | negative | - | - | False | - | - | - | - | 0.1 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-081 | negative | - | - | False | - | - | - | - | 0.1 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-082 | negative | - | - | False | - | - | - | - | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-083 | negative | - | - | True | - | - | 0.000 | - | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-084 | negative | - | - | False | - | - | - | - | 0.1 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-085 | negative | - | - | False | - | - | - | - | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |
| ge-086 | negative | - | - | True | - | - | 0.000 | - | 0.2 | judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized |

## Sample interactions -- what worked, what didn't

Full question/answer/judge-rationale transcript for every example in this run, in place of raw numbers alone.

### ge-001 [single_hop] -- ISSUE -- over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What did we decide about the pricing tiers?

**Answer:** Launch with 5 pricing tiers: Free, Starter, Growth, Business, Enterprise. Original plan to capture more price points across customer segments.

**Cited:** 4b8d1cb9-f88d-5dc7-be65-bc677ff0de09

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-002 [paraphrase] -- ISSUE -- over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How many pricing plans do we offer customers now?

**Answer:** Launch with 5 pricing tiers: Free, Starter, Growth, Business, Enterprise. Original plan to capture more price points across customer segments.

**Cited:** 4b8d1cb9-f88d-5dc7-be65-bc677ff0de09

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-003 [temporal] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What did we originally decide about pricing tiers, before the current approach?

**Answer:** Launch with 5 pricing tiers: Free, Starter, Growth, Business, Enterprise. Original plan to capture more price points across customer segments.

**Cited:** 4b8d1cb9-f88d-5dc7-be65-bc677ff0de09

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-004 [multi_hop] -- ISSUE -- under-cited (recall 0.50); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's the current decision on pricing tiers and how did we get there?

**Answer:** Launch with 5 pricing tiers: Free, Starter, Growth, Business, Enterprise. Original plan to capture more price points across customer segments.

**Cited:** 4b8d1cb9-f88d-5dc7-be65-bc677ff0de09

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-005 [single_hop] -- ISSUE -- over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What did we decide about the pricing tiers?

**Answer:** Launch with 5 pricing tiers: Free, Starter, Growth, Business, Enterprise. Original plan to capture more price points across customer segments.

**Cited:** 24172dc8-f418-584e-bd24-b814d8a59dc0

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-006 [paraphrase] -- ISSUE -- over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How many pricing plans do we offer customers now?

**Answer:** Launch with 5 pricing tiers: Free, Starter, Growth, Business, Enterprise. Original plan to capture more price points across customer segments.

**Cited:** 24172dc8-f418-584e-bd24-b814d8a59dc0

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-007 [temporal] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What did we originally decide about pricing tiers, before the current approach?

**Answer:** Launch with 5 pricing tiers: Free, Starter, Growth, Business, Enterprise. Original plan to capture more price points across customer segments.

**Cited:** 24172dc8-f418-584e-bd24-b814d8a59dc0

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-008 [multi_hop] -- ISSUE -- under-cited (recall 0.50); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's the current decision on pricing tiers and how did we get there?

**Answer:** Launch with 5 pricing tiers: Free, Starter, Growth, Business, Enterprise. Original plan to capture more price points across customer segments.

**Cited:** 24172dc8-f418-584e-bd24-b814d8a59dc0

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-009 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Which vendor did we choose for background checks?

**Answer:** Selected Checkr as the background check vendor. Checkr's under-24h turnaround beat Sterling's ~3 days; cost was comparable.

**Cited:** d3d1754f-8389-5828-97a4-7273bf67dc1a

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-010 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Who's running our candidate screening these days?

**Answer:** Selected Checkr as the background check vendor. Checkr's under-24h turnaround beat Sterling's ~3 days; cost was comparable.

**Cited:** d3d1754f-8389-5828-97a4-7273bf67dc1a

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-011 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Which vendor did we choose for background checks?

**Answer:** Selected Checkr as the background check vendor. Checkr's under-24h turnaround beat Sterling's ~3 days; cost was comparable.

**Cited:** f5c4b9c4-bf19-55e0-8ef0-b182bdcad28b

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-012 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Who's running our candidate screening these days?

**Answer:** Selected Checkr as the background check vendor. Checkr's under-24h turnaround beat Sterling's ~3 days; cost was comparable.

**Cited:** f5c4b9c4-bf19-55e0-8ef0-b182bdcad28b

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-013 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's our on-call rotation policy?

**Answer:** Adopt a weekly on-call rotation across the backend team with a secondary escalation on-call. The March outage went unacknowledged 40 minutes under a single on-call; a secondary catches missed acks.

**Cited:** d58f8310-71d8-5f18-b82a-50bfb616a432

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-014 [paraphrase] -- ISSUE -- over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** If the primary on-call doesn't respond, who gets paged next?

**Answer:** Use Postgres as the primary datastore for the new service. Needed real multi-table transactional guarantees; Mongo's transaction model was a weaker fit.

**Cited:** f0ab8759-3118-5562-a139-5c97c355a7b3

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-015 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's our on-call rotation policy?

**Answer:** Adopt a weekly on-call rotation across the backend team with a secondary escalation on-call. The March outage went unacknowledged 40 minutes under a single on-call; a secondary catches missed acks.

**Cited:** 259a5e95-63c4-57f9-8cbb-8950c68d28e5

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-016 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** If the primary on-call doesn't respond, who gets paged next?

**Answer:** Adopt a weekly on-call rotation across the backend team with a secondary escalation on-call. The March outage went unacknowledged 40 minutes under a single on-call; a secondary catches missed acks.

**Cited:** 259a5e95-63c4-57f9-8cbb-8950c68d28e5

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-017 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Is there a deploy freeze before releases?

**Answer:** Enforce a 48-hour deploy freeze window before any tagged release. Two consecutive Friday deploys caused weekend incidents; exceptions require director sign-off.

**Cited:** 7544462a-8fec-59e2-8059-122da7473a16

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-018 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Can I ship code right before a big release goes out?

**Answer:** Enforce a 48-hour deploy freeze window before any tagged release. Two consecutive Friday deploys caused weekend incidents; exceptions require director sign-off.

**Cited:** 7544462a-8fec-59e2-8059-122da7473a16

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-019 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Is there a deploy freeze before releases?

**Answer:** Enforce a 48-hour deploy freeze window before any tagged release. Two consecutive Friday deploys caused weekend incidents; exceptions require director sign-off.

**Cited:** 28fe5907-827f-5d88-bfb3-100ce4e82245

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-020 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Can I ship code right before a big release goes out?

**Answer:** Enforce a 48-hour deploy freeze window before any tagged release. Two consecutive Friday deploys caused weekend incidents; exceptions require director sign-off.

**Cited:** 28fe5907-827f-5d88-bfb3-100ce4e82245

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-021 [single_hop] -- ISSUE -- over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What database are we using for the new service?

**Answer:** Considered Mongo as the datastore for the new service. Rejected -- multi-document transaction support felt bolted-on for this access pattern.

**Cited:** 6106a591-1393-51fb-9610-af744f072135

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-022 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Postgres or Mongo -- what did we land on for the backend?

**Answer:** Use Postgres as the primary datastore for the new service. Needed real multi-table transactional guarantees; Mongo's transaction model was a weaker fit.

**Cited:** f0ab8759-3118-5562-a139-5c97c355a7b3

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-023 [ambiguous_entity] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Between Postgres and Mongo, which one did we actually pick?

**Answer:** Use Postgres as the primary datastore for the new service. Needed real multi-table transactional guarantees; Mongo's transaction model was a weaker fit.

**Cited:** f0ab8759-3118-5562-a139-5c97c355a7b3

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-024 [single_hop] -- ISSUE -- over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What database are we using for the new service?

**Answer:** Considered Mongo as the datastore for the new service. Rejected -- multi-document transaction support felt bolted-on for this access pattern.

**Cited:** 51daed2e-f872-52c0-8c17-edd37fddd65b

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-025 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Postgres or Mongo -- what did we land on for the backend?

**Answer:** Use Postgres as the primary datastore for the new service. Needed real multi-table transactional guarantees; Mongo's transaction model was a weaker fit.

**Cited:** caa44e05-e032-5baf-979c-d90579c1b44e

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-026 [ambiguous_entity] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Between Postgres and Mongo, which one did we actually pick?

**Answer:** Use Postgres as the primary datastore for the new service. Needed real multi-table transactional guarantees; Mongo's transaction model was a weaker fit.

**Cited:** caa44e05-e032-5baf-979c-d90579c1b44e

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-027 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How long do we keep raw ingested events before deleting them?

**Answer:** Retain raw ingested events for 30 days before deletion. Balances debugging/replay needs against storage cost and data minimization.

**Cited:** 8250bd78-95f9-5b8f-ba08-5575d1043243

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-028 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's the TTL on the unprocessed event data?

**Answer:** Retain raw ingested events for 30 days before deletion. Balances debugging/replay needs against storage cost and data minimization.

**Cited:** 8250bd78-95f9-5b8f-ba08-5575d1043243

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-029 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How long do we keep raw ingested events before deleting them?

**Answer:** Retain raw ingested events for 30 days before deletion. Balances debugging/replay needs against storage cost and data minimization.

**Cited:** 41ef0a6e-ff8a-51ce-a8a6-40600974bada

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-030 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's the TTL on the unprocessed event data?

**Answer:** Retain raw ingested events for 30 days before deletion. Balances debugging/replay needs against storage cost and data minimization.

**Cited:** 41ef0a6e-ff8a-51ce-a8a6-40600974bada

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-031 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How long are application logs kept?

**Answer:** Retain application logs for 90 days hot, then 1 year in cold storage. 90 days covers typical post-mortem windows; cold storage covers audit needs.

**Cited:** dbcd2ffb-2959-50ca-8fa0-01bb37ab3657

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-032 [paraphrase] -- ISSUE -- expected decision never retrieved; under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's our log archival window?

**Answer:** There's no recorded decision that answers this question.

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-033 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How long are application logs kept?

**Answer:** Retain application logs for 90 days hot, then 1 year in cold storage. 90 days covers typical post-mortem windows; cold storage covers audit needs.

**Cited:** 64f34bc7-0998-5912-be7a-f31b637eb11c

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-034 [paraphrase] -- ISSUE -- expected decision never retrieved; under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's our log archival window?

**Answer:** There's no recorded decision that answers this question.

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-035 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's our remote work policy?

**Answer:** Adopt a remote-first policy with no mandatory office days; teams may set optional in-person cadences. Matches recruiting commitments made to candidates this quarter.

**Cited:** 391079c8-1efe-5d02-8632-4983dbf02f74

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-036 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Do I have to come into the office on any specific days?

**Answer:** Adopt a remote-first policy with no mandatory office days; teams may set optional in-person cadences. Matches recruiting commitments made to candidates this quarter.

**Cited:** 391079c8-1efe-5d02-8632-4983dbf02f74

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-037 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's our remote work policy?

**Answer:** Adopt a remote-first policy with no mandatory office days; teams may set optional in-person cadences. Matches recruiting commitments made to candidates this quarter.

**Cited:** 99eca7f8-8604-5674-9560-685a52136622

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-038 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Do I have to come into the office on any specific days?

**Answer:** Adopt a remote-first policy with no mandatory office days; teams may set optional in-person cadences. Matches recruiting commitments made to candidates this quarter.

**Cited:** 99eca7f8-8604-5674-9560-685a52136622

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-039 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Do we require a bar-raiser for engineering hires?

**Answer:** Require independent bar-raiser sign-off, outside the hiring team, on every engineering offer. Introduced after two mis-hires last quarter.

**Cited:** 28ba5e8e-2086-5827-88b4-12a44e816714

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-040 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Who has to approve an engineering offer besides the hiring manager?

**Answer:** Require independent bar-raiser sign-off, outside the hiring team, on every engineering offer. Introduced after two mis-hires last quarter.

**Cited:** 28ba5e8e-2086-5827-88b4-12a44e816714

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-041 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Do we require a bar-raiser for engineering hires?

**Answer:** Require independent bar-raiser sign-off, outside the hiring team, on every engineering offer. Introduced after two mis-hires last quarter.

**Cited:** cdd6a9ee-39db-52fc-b39c-9af1b627d7b4

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-042 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Who has to approve an engineering offer besides the hiring manager?

**Answer:** Require independent bar-raiser sign-off, outside the hiring team, on every engineering offer. Introduced after two mis-hires last quarter.

**Cited:** cdd6a9ee-39db-52fc-b39c-9af1b627d7b4

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-043 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's our process after a major incident?

**Answer:** Require a blameless postmortem within 3 business days for every SEV1/SEV2 incident. Several undocumented Q4 SEV2s recurred within weeks with no follow-up.

**Cited:** fcfcef2d-ebae-589f-aef3-3faff4a49441

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-044 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Do we write anything up after a SEV1?

**Answer:** Require a blameless postmortem within 3 business days for every SEV1/SEV2 incident. Several undocumented Q4 SEV2s recurred within weeks with no follow-up.

**Cited:** fcfcef2d-ebae-589f-aef3-3faff4a49441

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-045 [single_hop] -- ISSUE -- over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's our process after a major incident?

**Answer:** Require independent bar-raiser sign-off, outside the hiring team, on every engineering offer. Introduced after two mis-hires last quarter.

**Cited:** 28ba5e8e-2086-5827-88b4-12a44e816714

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-046 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Do we write anything up after a SEV1?

**Answer:** Require a blameless postmortem within 3 business days for every SEV1/SEV2 incident. Several undocumented Q4 SEV2s recurred within weeks with no follow-up.

**Cited:** 8eabfe66-7818-5b2c-bbc4-8f68d912b418

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-047 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How do we roll out new features?

**Answer:** Roll out new features behind flags at 5% -> 25% -> 100% over a week, with auto-rollback on 2x error rate for 10 minutes. Gives a controlled rollout with an automatic, objective rollback trigger.

**Cited:** 7a434f0f-b4f0-5c2d-9d87-2be8a52609ec

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-048 [paraphrase] -- ISSUE -- over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What percentage of users see a brand-new feature on day one?

**Answer:** Considered Mongo as the datastore for the new service. Rejected -- multi-document transaction support felt bolted-on for this access pattern.

**Cited:** 6106a591-1393-51fb-9610-af744f072135

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-049 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How do we roll out new features?

**Answer:** Roll out new features behind flags at 5% -> 25% -> 100% over a week, with auto-rollback on 2x error rate for 10 minutes. Gives a controlled rollout with an automatic, objective rollback trigger.

**Cited:** 51cf5869-1982-5acb-a0b5-daf87031a1d2

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-050 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What percentage of users see a brand-new feature on day one?

**Answer:** Roll out new features behind flags at 5% -> 25% -> 100% over a week, with auto-rollback on 2x error rate for 10 minutes. Gives a controlled rollout with an automatic, objective rollback trigger.

**Cited:** 51cf5869-1982-5acb-a0b5-daf87031a1d2

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-051 [single_hop] -- ISSUE -- over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's our refund policy for customers?

**Answer:** Adopt a remote-first policy with no mandatory office days; teams may set optional in-person cadences. Matches recruiting commitments made to candidates this quarter.

**Cited:** 391079c8-1efe-5d02-8632-4983dbf02f74

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-052 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Can support just refund someone without asking a manager?

**Answer:** Support may issue full refunds within 14 days with no questions asked; support leads can approve up to $500 beyond that without escalation. Reduces unnecessary escalations to leadership for routine refund cases.

**Cited:** 4682b2e5-39ac-5e04-9c75-1025da238235

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-053 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What's our refund policy for customers?

**Answer:** Support may issue full refunds within 14 days with no questions asked; support leads can approve up to $500 beyond that without escalation. Reduces unnecessary escalations to leadership for routine refund cases.

**Cited:** 11c39d22-7c20-5d25-a8be-f90fb5084b22

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-054 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Can support just refund someone without asking a manager?

**Answer:** Support may issue full refunds within 14 days with no questions asked; support leads can approve up to $500 beyond that without escalation. Reduces unnecessary escalations to leadership for routine refund cases.

**Cited:** 11c39d22-7c20-5d25-a8be-f90fb5084b22

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-055 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How is the marketing budget split this quarter?

**Answer:** Shift Q2 marketing budget split to 60% content/SEO, 40% paid social. Last quarter's paid social spend had a weak CAC; content channel performed better per dollar.

**Cited:** 82257dd0-6873-51af-8499-88006eb7a1a7

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-056 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Are we spending more on content or paid ads right now?

**Answer:** Shift Q2 marketing budget split to 60% content/SEO, 40% paid social. Last quarter's paid social spend had a weak CAC; content channel performed better per dollar.

**Cited:** 82257dd0-6873-51af-8499-88006eb7a1a7

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-057 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How is the marketing budget split this quarter?

**Answer:** Shift Q2 marketing budget split to 60% content/SEO, 40% paid social. Last quarter's paid social spend had a weak CAC; content channel performed better per dollar.

**Cited:** 201d15c1-9e60-5d6b-9d3f-8aa1e5ab4ef4

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-058 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Are we spending more on content or paid ads right now?

**Answer:** Shift Q2 marketing budget split to 60% content/SEO, 40% paid social. Last quarter's paid social spend had a weak CAC; content channel performed better per dollar.

**Cited:** 201d15c1-9e60-5d6b-9d3f-8aa1e5ab4ef4

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-059 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What are the code review requirements for payments code?

**Answer:** Require at least one approval from outside the author's immediate team for changes to payments or auth code. A self-merged PR with no second reviewer caused a production incident.

**Cited:** 8828e780-a0c4-5fe4-98d4-a85c70098359

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-060 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Can someone on my own team approve my auth-related PR?

**Answer:** Require at least one approval from outside the author's immediate team for changes to payments or auth code. A self-merged PR with no second reviewer caused a production incident.

**Cited:** 8828e780-a0c4-5fe4-98d4-a85c70098359

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-061 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What are the code review requirements for payments code?

**Answer:** Require at least one approval from outside the author's immediate team for changes to payments or auth code. A self-merged PR with no second reviewer caused a production incident.

**Cited:** 0757cecb-41fd-51cd-9321-56ff4a4de02c

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-062 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Can someone on my own team approve my auth-related PR?

**Answer:** Require at least one approval from outside the author's immediate team for changes to payments or auth code. A self-merged PR with no second reviewer caused a production incident.

**Cited:** 0757cecb-41fd-51cd-9321-56ff4a4de02c

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-063 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Is MFA required for internal tools?

**Answer:** Make MFA mandatory for all internal tools within 30 days, including contractors, with no exceptions. Prompted by a phishing attempt the prior month.

**Cited:** 89c2e663-0179-5477-a077-fe057fb4d6bf

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-064 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Do contractors also need two-factor auth on our systems?

**Answer:** Make MFA mandatory for all internal tools within 30 days, including contractors, with no exceptions. Prompted by a phishing attempt the prior month.

**Cited:** 89c2e663-0179-5477-a077-fe057fb4d6bf

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-065 [single_hop] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Is MFA required for internal tools?

**Answer:** Make MFA mandatory for all internal tools within 30 days, including contractors, with no exceptions. Prompted by a phishing attempt the prior month.

**Cited:** 6b7fb84b-71ca-5d9a-a191-1b6647fcb534

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-066 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Do contractors also need two-factor auth on our systems?

**Answer:** Make MFA mandatory for all internal tools within 30 days, including contractors, with no exceptions. Prompted by a phishing attempt the prior month.

**Cited:** 6b7fb84b-71ca-5d9a-a191-1b6647fcb534

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-067 [single_hop] -- ISSUE -- expected decision never retrieved; over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How often does the team have standup now?

**Answer:** Require independent bar-raiser sign-off, outside the hiring team, on every engineering offer. Introduced after two mis-hires last quarter.

**Cited:** cdd6a9ee-39db-52fc-b39c-9af1b627d7b4

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-068 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Is standup a daily thing or not anymore?

**Answer:** Cut daily standups to 3x/week (Mon/Wed/Fri), with async updates the other two days. Daily standups had become a low-value status report format.

**Cited:** 00e0bca4-bded-5194-9c8b-7d35585de1ec

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-069 [single_hop] -- ISSUE -- expected decision never retrieved; over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How often does the team have standup now?

**Answer:** Require independent bar-raiser sign-off, outside the hiring team, on every engineering offer. Introduced after two mis-hires last quarter.

**Cited:** 28ba5e8e-2086-5827-88b4-12a44e816714

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-070 [paraphrase] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** Is standup a daily thing or not anymore?

**Answer:** Cut daily standups to 3x/week (Mon/Wed/Fri), with async updates the other two days. Daily standups had become a low-value status report format.

**Cited:** 9f520fbc-36c7-5f42-a435-a32afdf4ffcc

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-071 [ambiguous_entity] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How long do we retain data before deleting or archiving it?

**Answer:** Retain raw ingested events for 30 days before deletion. Balances debugging/replay needs against storage cost and data minimization.

**Cited:** 8250bd78-95f9-5b8f-ba08-5575d1043243

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-072 [ambiguous_entity] -- ISSUE -- judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** How long do we retain data before deleting or archiving it?

**Answer:** Retain raw ingested events for 30 days before deletion. Balances debugging/replay needs against storage cost and data minimization.

**Cited:** 41ef0a6e-ff8a-51ce-a8a6-40600974bada

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-073 [single_hop] -- ISSUE -- expected decision never retrieved; under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What database did Aurora Robotics pick for the warehouse arm firmware?

**Answer:** There's no recorded decision that answers this question.

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-074 [single_hop] -- ISSUE -- over-cited (precision 0.00); under-cited (recall 0.00); judge call failed: judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

**Question:** What database did Cobalt Analytics pick for the reporting service?

**Answer:** Considered Mongo as the datastore for the new service. Rejected -- multi-document transaction support felt bolted-on for this access pattern.

**Cited:** 51daed2e-f872-52c0-8c17-edd37fddd65b

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-075 [negative] -- WORKED -- correctly declined to answer (true negative)

**Question:** Which vendor did we choose for background checks?

**Answer:** There's no recorded decision that answers this question.

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-076 [negative] -- ISSUE -- fabricated an answer where none should exist (false positive)

**Question:** Is there a deploy freeze before releases?

**Answer:** Retain raw ingested events for 30 days before deletion. Balances debugging/replay needs against storage cost and data minimization.

**Cited:** 8250bd78-95f9-5b8f-ba08-5575d1043243

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-077 [negative] -- WORKED -- correctly declined to answer (true negative)

**Question:** What's our remote work policy?

**Answer:** There's no recorded decision that answers this question.

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-078 [negative] -- ISSUE -- fabricated an answer where none should exist (false positive)

**Question:** What's our on-call rotation policy?

**Answer:** Adopt a remote-first policy with no mandatory office days; teams may set optional in-person cadences. Matches recruiting commitments made to candidates this quarter.

**Cited:** 391079c8-1efe-5d02-8632-4983dbf02f74

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-079 [negative] -- ISSUE -- fabricated an answer where none should exist (false positive)

**Question:** Is there a deploy freeze before releases?

**Answer:** Retain raw ingested events for 30 days before deletion. Balances debugging/replay needs against storage cost and data minimization.

**Cited:** 41ef0a6e-ff8a-51ce-a8a6-40600974bada

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-080 [negative] -- WORKED -- correctly declined to answer (true negative)

**Question:** What database are we using for the new service?

**Answer:** There's no recorded decision that answers this question.

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-081 [negative] -- WORKED -- correctly declined to answer (true negative)

**Question:** What did we decide about the pricing tiers?

**Answer:** There's no recorded decision that answers this question.

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-082 [negative] -- WORKED -- correctly declined to answer (true negative)

**Question:** What's our on-call rotation policy?

**Answer:** There's no recorded decision that answers this question.

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-083 [negative] -- ISSUE -- fabricated an answer where none should exist (false positive)

**Question:** How long do we keep raw ingested events before deleting them?

**Answer:** Enforce a 48-hour deploy freeze window before any tagged release. Two consecutive Friday deploys caused weekend incidents; exceptions require director sign-off.

**Cited:** 7544462a-8fec-59e2-8059-122da7473a16

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-084 [negative] -- WORKED -- correctly declined to answer (true negative)

**Question:** What did we decide about the pricing tiers?

**Answer:** There's no recorded decision that answers this question.

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-085 [negative] -- WORKED -- correctly declined to answer (true negative)

**Question:** Which vendor did we choose for background checks?

**Answer:** There's no recorded decision that answers this question.

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized

### ge-086 [negative] -- ISSUE -- fabricated an answer where none should exist (false positive)

**Question:** What database are we using for the new service?

**Answer:** Roll out new features behind flags at 5% -> 25% -> 100% over a week, with auto-rollback on 2x error rate for 10 minutes. Gives a controlled rollout with an automatic, objective rollback trigger.

**Cited:** 51cf5869-1982-5acb-a0b5-daf87031a1d2

**Judge error:** judge call failed: JudgeError: Sonnet judge call failed: AuthenticationError: Unauthorized
