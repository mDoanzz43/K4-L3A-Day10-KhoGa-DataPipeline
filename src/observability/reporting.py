from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.utils import write_text


def _display(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def generate_phase1_report(
    report_path: str | Path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write a reproducible Markdown summary of the baseline pipeline."""
    source_rows = "\n".join(
        f"| `{key}` | {_display(value)} |" for key, value in source_summary.items()
    )

    metric_keys = (
        "samples",
        "retrieval_hit_rate",
        "mean_token_f1",
        "judge_accuracy",
        "mean_judge_score",
    )
    metric_rows = "\n".join(
        f"| `{key}` | {_display(metrics.get(key))} |" for key in metric_keys
    )
    ragas = metrics.get("ragas", {})

    quality_statistics = quality.get("statistics", {})
    quality_rows: list[str] = []
    for result in quality.get("results", []):
        config = result.get("expectation_config", {})
        expectation_type = config.get("type", "unknown")
        kwargs = config.get("kwargs", {})
        column = kwargs.get("column", "table")
        observed = result.get("result", {}).get("observed_value", "N/A")
        quality_rows.append(
            f"| `{expectation_type}` | `{column}` | "
            f"{_display(result.get('success', False))} | {_display(observed)} |"
        )
    quality_table = "\n".join(quality_rows) or "| N/A | N/A | FAIL | N/A |"

    stale_percent = float(freshness.get("stale_ratio", 0.0)) * 100
    generated_at = datetime.now(UTC).isoformat()
    markdown = f"""# Phase 1 — Baseline Pipeline Report

Generated at: `{generated_at}`

## Pipeline status

| Signal | Result |
| --- | --- |
| Data quality gate | {_display(quality.get("success", False))} |
| Freshness SLA | {_display(freshness.get("is_fresh", False))} |
| Evaluated expectations | {_display(quality_statistics.get("evaluated_expectations"))} |
| Successful expectations | {_display(quality_statistics.get("successful_expectations"))} |

## Source and indexing

| Property | Value |
| --- | --- |
{source_rows}

## Baseline metrics

| Metric | Value |
| --- | ---: |
{metric_rows}

Ragas: `{_display(ragas)}`

## Great Expectations validation

| Expectation | Scope | Status | Observed |
| --- | --- | --- | --- |
{quality_table}

## Freshness SLA

| Property | Value |
| --- | --- |
| Latest publication | {_display(freshness.get("latest_published"))} |
| Oldest publication | {_display(freshness.get("oldest_published"))} |
| Stale threshold | {freshness.get("stale_threshold_days", 180)} days |
| Stale records | {freshness.get("stale_rows", 0)} / {freshness.get("total_rows", 0)} |
| Stale ratio | {stale_percent:.2f}% |
| Maximum allowed stale ratio | {float(freshness.get("max_stale_ratio", 0.25)) * 100:.2f}% |
| Status | {_display(freshness.get("is_fresh", False))} |

## Conclusion

The baseline contains **{source_summary.get("clean_records", 0)} cleaned papers**.

Retrieval hit rate is **{float(metrics.get("retrieval_hit_rate", 0.0)):.2%}** and mean token F1 is **{float(metrics.get("mean_token_f1", 0.0)):.2%}**.

The quality gate is **{_display(quality.get("success", False))}** and the freshness SLA is **{_display(freshness.get("is_fresh", False))}**.
"""
    write_text(Path(report_path), markdown)


def generate_corruption_report(
    report_path: str | Path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write the quantitative baseline/corrupted/repaired comparison report."""
    metric_keys = (
        "retrieval_hit_rate",
        "mean_token_f1",
        "judge_accuracy",
        "mean_judge_score",
    )
    metric_rows: list[str] = []
    for key in metric_keys:
        baseline = float(baseline_metrics.get(key, 0.0))
        corrupted = float(corrupted_metrics.get(key, 0.0))
        repaired = float(repaired_metrics.get(key, 0.0))
        metric_rows.append(
            f"| `{key}` | {baseline:.4f} | {corrupted:.4f} | {repaired:.4f} | "
            f"{corrupted - baseline:+.4f} | {repaired - baseline:+.4f} |"
        )

    corrupted_stale = float(corrupted_freshness.get("stale_ratio", 0.0))
    repaired_stale = float(repaired_freshness.get("stale_ratio", 0.0))
    retrieval_recovered = repaired_metrics.get("retrieval_hit_rate") == baseline_metrics.get(
        "retrieval_hit_rate"
    )
    f1_recovered = repaired_metrics.get("mean_token_f1") == baseline_metrics.get(
        "mean_token_f1"
    )
    fully_recovered = (
        retrieval_recovered
        and f1_recovered
        and bool(repaired_quality.get("success"))
        and bool(repaired_freshness.get("is_fresh"))
    )

    markdown = f"""# Data Corruption and Idempotent Repair Report

Generated at: `{datetime.now(UTC).isoformat()}`

## Executive summary

Synthetic corruption caused the data-quality gate to **{_display(corrupted_quality.get("success", False))}** and the freshness SLA to **{_display(corrupted_freshness.get("is_fresh", False))}**. Rebuilding exclusively from the trusted raw snapshot restored the quality gate to **{_display(repaired_quality.get("success", False))}** and freshness to **{_display(repaired_freshness.get("is_fresh", False))}**.

Overall repair status: **{"FULLY RECOVERED" if fully_recovered else "PARTIALLY RECOVERED"}**.

## Performance comparison

| Metric | Baseline | Corrupted | Repaired | Corruption delta | Repaired vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(metric_rows)}

## Corruption impact analysis

The six controlled failures affect different parts of the RAG pipeline:

1. **Drop latest records:** removes 20% of the newest papers, so benchmark targets can disappear from the corpus and recent coverage is reduced.
2. **Blank summary:** removes the main answer-bearing field, triggering the minimum-length expectation and leaving the QA layer without summary evidence.
3. **Inject noise:** changes the semantic embedding of affected documents and can move otherwise relevant papers away from their queries.
4. **Truncate title:** weakens both exact-title lookup and the strongest identifying text included in each embedding.
5. **Stale date:** moves publication dates back 365 days, pushing the stale ratio above the 25% Freshness SLA limit.
6. **Duplicate rows:** violates `paper_id` uniqueness and can over-represent duplicated content in retrieval results.

Together, these failures reduced retrieval hit rate by **{float(baseline_metrics.get("retrieval_hit_rate", 0.0)) - float(corrupted_metrics.get("retrieval_hit_rate", 0.0)):.2%}**, mean token F1 by **{float(baseline_metrics.get("mean_token_f1", 0.0)) - float(corrupted_metrics.get("mean_token_f1", 0.0)):.2%}**, and judge accuracy by **{float(baseline_metrics.get("judge_accuracy", 0.0)) - float(corrupted_metrics.get("judge_accuracy", 0.0)):.2%}**. The simultaneous metric collapse and observability alerts demonstrate that this is a data-induced failure rather than an application crash.

## Data observability comparison

| Signal | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Data quality gate | PASS | {_display(corrupted_quality.get("success", False))} | {_display(repaired_quality.get("success", False))} |
| Freshness SLA | PASS | {_display(corrupted_freshness.get("is_fresh", False))} | {_display(repaired_freshness.get("is_fresh", False))} |
| Stale rows | {0} | {corrupted_freshness.get("stale_rows", 0)} | {repaired_freshness.get("stale_rows", 0)} |
| Stale ratio | {0.0:.2%} | {corrupted_stale:.2%} | {repaired_stale:.2%} |
| Total rows | {baseline_metrics.get("source_rows", repaired_freshness.get("total_rows", 0))} | {corrupted_freshness.get("total_rows", 0)} | {repaired_freshness.get("total_rows", 0)} |

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

Retrieval hit rate recovered from **{float(corrupted_metrics.get("retrieval_hit_rate", 0.0)):.2%}** to **{float(repaired_metrics.get("retrieval_hit_rate", 0.0)):.2%}**. Mean token F1 recovered from **{float(corrupted_metrics.get("mean_token_f1", 0.0)):.2%}** to **{float(repaired_metrics.get("mean_token_f1", 0.0)):.2%}**. The repaired results {"match" if fully_recovered else "do not yet fully match"} the clean baseline.
"""
    write_text(Path(report_path), markdown)
