from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import safe_slug, write_json

MIN_ROW_COUNT = 5
MAX_ROW_COUNT = 5_000
MIN_SUMMARY_LENGTH = 30
MAX_STALE_RATIO = 0.25


def _quality_report_path(settings: Settings, report_name: str) -> Path:
    """Return a safe, predictable path for a named quality report."""
    normalized_name = safe_slug(report_name)
    configured_paths = {
        "baseline": settings.paths.baseline_quality_report,
        "corrupted": settings.paths.corrupted_quality_report,
    }
    return configured_paths.get(
        normalized_name,
        settings.paths.quality_dir / f"{normalized_name}_quality_report.json",
    )


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate a paper dataframe with Great Expectations 1.x.

    The context is deliberately ephemeral: validation is performed in memory and
    only the compact JSON report is persisted under ``data/quality``.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    normalized_name = safe_slug(report_name)
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    suite = gx.ExpectationSuite(name=f"{normalized_name}_papers_suite")
    suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=MIN_ROW_COUNT,
            max_value=MAX_ROW_COUNT,
        )
    )
    for column in ("paper_id", "title", "text_for_embedding"):
        suite.add_expectation(
            gx.expectations.ExpectColumnValuesToNotBeNull(column=column)
        )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="summary",
            min_value=MIN_SUMMARY_LENGTH,
        )
    )

    validation = batch.validate(suite)
    report = validation.to_json_dict()
    report["report_name"] = normalized_name
    report["generated_at"] = datetime.now(UTC).isoformat()
    report["freshness"] = _freshness_payload(df, settings)

    write_json(_quality_report_path(settings, report_name), report)
    return report


def _freshness_payload(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    """Calculate freshness metrics without performing file I/O."""
    total_rows = len(df)

    if "age_days" in df.columns:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
    else:
        ages = pd.Series(float("nan"), index=df.index, dtype="float64")

    stale_rows = int((ages > settings.freshness_threshold_days).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 0.0

    if "published" in df.columns:
        published = pd.to_datetime(df["published"], errors="coerce", utc=True).dropna()
    else:
        published = pd.Series(dtype="datetime64[ns, UTC]")

    latest = published.max().date().isoformat() if not published.empty else None
    oldest = published.min().date().isoformat() if not published.empty else None
    is_fresh = total_rows > 0 and stale_ratio <= MAX_STALE_RATIO

    return {
        "latest_published": latest,
        "oldest_published": oldest,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "stale_threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": MAX_STALE_RATIO,
        "is_fresh": is_fresh,
        "warning": None
        if is_fresh
        else "Freshness SLA failed: update the dataset with newer papers.",
    }


def build_freshness_report(
    df: pd.DataFrame,
    settings: Settings,
    report_path: str | Path,
) -> dict[str, Any]:
    """Build and persist the freshness SLA report for a paper dataframe."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    report = _freshness_payload(df, settings)
    report["generated_at"] = datetime.now(UTC).isoformat()
    write_json(Path(report_path), report)
    return report
