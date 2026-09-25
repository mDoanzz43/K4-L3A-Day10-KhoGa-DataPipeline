from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate the clean dataframe with an in-memory Great Expectations context."""
    import great_expectations as gx

    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    expectations = [
        gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id"),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="title"),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
        gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"),
        gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
    ]
    validation_results = [batch.validate(expectation) for expectation in expectations]
    checks = [
        {
            "expectation": result.expectation_config.type,
            "success": bool(result.success),
            "result": result.result,
        }
        for result in validation_results
    ]
    freshness_path = settings.paths.quality_dir / f"{report_name}_freshness_report.json"
    freshness = build_freshness_report(df, settings, freshness_path)
    payload = {
        "success": all(check["success"] for check in checks),
        "report_name": report_name,
        "checks": checks,
        "freshness": freshness,
    }
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Report whether more than one quarter of the dataset is older than the SLA."""
    published = pd.to_datetime(df.get("published"), errors="coerce", utc=True)
    ages = pd.to_numeric(df.get("age_days"), errors="coerce")
    total_rows = len(df)
    stale_rows = int((ages > settings.freshness_threshold_days).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    payload = {
        "latest_published": published.max().date().isoformat() if published.notna().any() else None,
        "oldest_published": published.min().date().isoformat() if published.notna().any() else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "freshness_threshold_days": settings.freshness_threshold_days,
        "is_fresh": stale_ratio <= 0.25,
    }
    write_json(report_path, payload)
    # Keep the configured canonical report current for the baseline pipeline.
    if report_path != settings.paths.freshness_report:
        write_json(settings.paths.freshness_report, payload)
    return payload
