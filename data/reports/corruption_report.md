# Data Corruption and Idempotent Repair Report

Generated at: `2026-09-25T09:33:15.073638+00:00`

## Executive summary

Synthetic corruption caused the data-quality gate to **FAIL** and the freshness SLA to **FAIL**. Rebuilding exclusively from the trusted raw snapshot restored the quality gate to **PASS** and freshness to **PASS**.

Overall repair status: **FULLY RECOVERED**.

## Performance comparison

| Metric | Baseline | Corrupted | Repaired | Corruption delta | Repaired vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0000 | 0.0000 | 1.0000 | -1.0000 | +0.0000 |
| `mean_token_f1` | 1.0000 | 0.2546 | 1.0000 | -0.7454 | +0.0000 |
| `judge_accuracy` | 1.0000 | 0.2000 | 1.0000 | -0.8000 | +0.0000 |
| `mean_judge_score` | 5.0000 | 1.8000 | 5.0000 | -3.2000 | +0.0000 |

## Corruption impact analysis

The six controlled failures affect different parts of the RAG pipeline:

1. **Drop latest records:** removes 20% of the newest papers, so benchmark targets can disappear from the corpus and recent coverage is reduced.
2. **Blank summary:** removes the main answer-bearing field, triggering the minimum-length expectation and leaving the QA layer without summary evidence.
3. **Inject noise:** changes the semantic embedding of affected documents and can move otherwise relevant papers away from their queries.
4. **Truncate title:** weakens both exact-title lookup and the strongest identifying text included in each embedding.
5. **Stale date:** moves publication dates back 365 days, pushing the stale ratio above the 25% Freshness SLA limit.
6. **Duplicate rows:** violates `paper_id` uniqueness and can over-represent duplicated content in retrieval results.

Together, these failures reduced retrieval hit rate by **100.00%**, mean token F1 by **74.54%**, and judge accuracy by **80.00%**. The simultaneous metric collapse and observability alerts demonstrate that this is a data-induced failure rather than an application crash.

## Data observability comparison

| Signal | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Data quality gate | PASS | FAIL | PASS |
| Freshness SLA | PASS | FAIL | PASS |
| Stale rows | 0 | 9 | 0 |
| Stale ratio | 0.00% | 42.86% | 0.00% |
| Total rows | 24 | 21 | 24 |

## Repair method

1. Discard the derived corrupted dataframe; it is never used as a repair source.
2. Reload immutable records from `data/raw/crossref_records.json` (falling back to `crossref_response.json`).
3. Re-run the deterministic cleaning rules and rebuild `text_for_embedding`.
4. Validate the repaired dataframe with the same GX suite and Freshness SLA.
5. Rebuild the isolated `papers-repaired` ChromaDB collection.
6. Evaluate with the unchanged `data/eval/test_set.json` benchmark.

Because repair is a pure rebuild from trusted raw input, repeated executions produce the same logical dataset and metrics without accumulating duplicate records in the active collection.

## Artifact evidence

- Corruption log: `data/results/corruption_log.json`
- Corrupted metrics: `data/results/corrupted_metrics.json`
- Repaired metrics: `data/results/repaired_metrics.json`
- Corrupted quality: `data/quality/corrupted_quality_report.json`
- Repaired quality: `data/quality/repaired_quality_report.json`
- Repaired dataset: `data/clean/papers_clean_repaired.json`
- Repaired embedding manifest: `data/embeddings/papers_embeddings_repaired.json`

## Conclusion

Retrieval hit rate recovered from **0.00%** to **100.00%**. Mean token F1 recovered from **25.46%** to **100.00%**. The repaired results match the clean baseline.
