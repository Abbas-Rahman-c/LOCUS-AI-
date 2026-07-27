# Benchmark Summary — Upgraded RAG Pipeline

## 1. Overall Metrics

| Metric | Value |
|---|---|
| Total benchmark queries | 60 |
| Pass rate | 42/60 |
| Recall@1 | 0.311 |
| Recall@3 | 0.578 |
| Recall@5 | 0.600 |
| MRR | 0.446 |
| Citation Precision | 0.484 |
| Citation Recall | 0.640 |
| Permission Accuracy | 1.000 |
| No-answer Accuracy | 0.889 |
| Average latency | 7,194 ms |

## 2. Per-query Results

| Query ID | Result | Failure Category |
|---|---|---|
| kw-01 | Pass | - |
| kw-02 | Pass | - |
| kw-03 | Pass | - |
| kw-04 | Pass | - |
| para-01 | Pass | - |
| para-02 | Pass | - |
| para-03 | Fail | Wrong Answer |
| para-04 | Pass | - |
| rat-01 | Pass | - |
| rat-02 | Pass | - |
| rat-03 | Pass | - |
| rat-04 | Pass | - |
| actor-01 | Pass | - |
| actor-02 | Pass | - |
| actor-03 | Pass | - |
| multi-01 | Fail | Wrong Answer |
| multi-02 | Pass | - |
| multi-03 | Fail | Wrong Answer |
| perm-01 | Pass | - |
| perm-02 | Pass | - |
| perm-03 | Pass | - |
| neg-01 | Pass | - |
| neg-02 | Pass | - |
| neg-03 | Pass | - |
| neg-04 | Pass | - |
| hyb-kw-01 | Pass | - |
| hyb-kw-02 | Fail | Reasonable No-Answer |
| hyb-kw-03 | Fail | Reasonable No-Answer |
| hyb-kw-04 | Fail | Wrong Answer |
| hyb-sem-01 | Pass | - |
| hyb-sem-02 | Pass | - |
| hyb-sem-03 | Pass | - |
| hyb-sem-04 | Pass | - |
| hyb-hyb-eng | Fail | Wrong Answer |
| hyb-hyb-fin | Pass | - |
| hyb-hyb-legal | Pass | - |
| hyb-hyb-security | Fail | Reasonable No-Answer |
| hyb-id-01 | Pass | - |
| hyb-id-02 | Pass | - |
| hyb-id-03 | Pass | - |
| hyb-id-04 | Fail | Reasonable No-Answer |
| hyb-acr-01 | Pass | - |
| hyb-acr-02 | Pass | - |
| hyb-acr-03 | Fail | Phrasing Mismatch |
| hyb-ent-01 | Pass | - |
| hyb-ent-02 | Fail | Wrong Answer |
| hyb-ent-03 | Fail | Reasonable No-Answer |
| hyb-dup-01 | Pass | - |
| hyb-dup-02 | Fail | Wrong Answer |
| hyb-dup-03 | Pass | - |
| hyb-multi-01 | Fail | Wrong Answer |
| hyb-multi-02 | Fail | Wrong Answer |
| hyb-multi-03 | Fail | Reasonable No-Answer |
| hyb-multi-04 | Fail | Phrasing Mismatch |
| hyb-perm-01 | Pass | - |
| hyb-perm-02 | Pass | - |
| hyb-perm-03 | Pass | - |
| hyb-neg-01 | Pass | - |
| hyb-neg-02 | Fail | Wrong Answer |
| hyb-neg-03 | Pass | - |

## 3. Reproducibility Note

The complete benchmark artifacts are provided separately as
`benchmark_artifacts.zip`. This archive contains the benchmark corpus,
ground truth, query definitions, load manifest, raw benchmark outputs,
per-query evaluation results, and supporting benchmark documentation
required to independently reproduce and verify the reported metrics.
These generated evaluation artifacts were intentionally excluded from Git
to keep this PR focused on the implementation changes.
