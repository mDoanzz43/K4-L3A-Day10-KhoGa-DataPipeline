# Phase 1 — Baseline Pipeline Report

Generated at: `2026-09-25T12:21:51.620749+00:00`

## Pipeline status

| Signal | Result |
| --- | --- |
| Data quality gate | PASS |
| Freshness SLA | PASS |
| Evaluated expectations | 6 |
| Successful expectations | 6 |

## Source and indexing

| Property | Value |
| --- | --- |
| `source` | Crossref REST API |
| `source_mode` | cached raw records |
| `query` | agentic retrieval augmented generation large language model |
| `raw_records` | 24 |
| `clean_records` | 24 |
| `dropped_records` | 0 |
| `embedding_model` | sentence-transformers/all-MiniLM-L6-v2 |
| `chroma_collection` | papers-baseline |
| `indexed_documents` | 24 |
| `evaluation_questions` | 10 |

## Baseline metrics

| Metric | Value |
| --- | ---: |
| `samples` | 10 |
| `retrieval_hit_rate` | 1.0000 |
| `mean_token_f1` | 0.9044 |
| `judge_accuracy` | 0.9000 |
| `mean_judge_score` | 4.4000 |

Ragas: `{'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'}`

## Great Expectations validation

| Expectation | Scope | Status | Observed |
| --- | --- | --- | --- |
| `expect_table_row_count_to_be_between` | `table` | PASS | 24 |
| `expect_column_values_to_not_be_null` | `paper_id` | PASS | N/A |
| `expect_column_values_to_be_unique` | `paper_id` | PASS | N/A |
| `expect_column_values_to_not_be_null` | `title` | PASS | N/A |
| `expect_column_values_to_not_be_null` | `text_for_embedding` | PASS | N/A |
| `expect_column_value_lengths_to_be_between` | `summary` | PASS | N/A |

## Freshness SLA

| Property | Value |
| --- | --- |
| Latest publication | 2026-07-22 |
| Oldest publication | 2026-03-28 |
| Stale threshold | 180 days |
| Stale records | 1 / 24 |
| Stale ratio | 4.17% |
| Maximum allowed stale ratio | 25.00% |
| Status | PASS |

## Conclusion

The baseline contains **24 cleaned papers**.

Retrieval hit rate is **100.00%** and mean token F1 is **90.44%**.

The quality gate is **PASS** and the freshness SLA is **PASS**.
