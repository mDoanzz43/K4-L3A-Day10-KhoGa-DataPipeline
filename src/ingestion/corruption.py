from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import write_json

NOISE = "@@@ ### CORRUPTED NOISE 9xQ!$% ### @@@"


def _paper_ids(df: pd.DataFrame, indexes: list[Any]) -> list[str]:
    return [str(df.at[index, "paper_id"]) for index in indexes]


def _rebuild_embedding_text(df: pd.DataFrame) -> None:
    df["summary_chars"] = df["summary"].fillna("").astype(str).str.len()
    df["text_for_embedding"] = df.apply(
        lambda row: "\n".join(
            (
                f"Title: {row['title']}".rstrip(),
                f"Authors: {row['authors_joined']}".rstrip(),
                f"Published: {row['published']}".rstrip(),
                f"Categories: {row['categories_joined']}".rstrip(),
                f"Summary: {row['summary']}".rstrip(),
            )
        ),
        axis=1,
    )


def corrupt_clean_dataframe(
    df: pd.DataFrame,
    output_log_path: str | Path,
) -> pd.DataFrame:
    """Apply six deterministic corruption scenarios and write an audit log."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if df.empty:
        raise ValueError("Cannot corrupt an empty dataframe")

    required = {
        "paper_id",
        "title",
        "summary",
        "published",
        "age_days",
        "authors_joined",
        "categories_joined",
        "text_for_embedding",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    scenarios: list[dict[str, Any]] = []

    published = pd.to_datetime(corrupted["published"], errors="coerce", utc=True)
    drop_count = max(1, ceil(len(corrupted) * 0.20))
    latest_indexes = published.sort_values(ascending=False).index[:drop_count].tolist()
    dropped_ids = _paper_ids(corrupted, latest_indexes)
    corrupted = corrupted.drop(index=latest_indexes).reset_index(drop=True)
    scenarios.append(
        {
            "type": "drop_latest_records",
            "description": "Removed the newest 20% of records by publication date.",
            "affected_rows": len(dropped_ids),
            "paper_ids": dropped_ids,
        }
    )

    affected_count = max(1, min(3, len(corrupted)))
    blank_indexes = list(corrupted.index[:affected_count])
    blank_ids = _paper_ids(corrupted, blank_indexes)
    corrupted.loc[blank_indexes, "summary"] = ""
    scenarios.append(
        {
            "type": "blank_summary",
            "description": "Replaced selected summaries with empty strings.",
            "affected_rows": len(blank_ids),
            "paper_ids": blank_ids,
        }
    )

    noise_start = affected_count
    noise_indexes = list(corrupted.index[noise_start : noise_start + affected_count])
    if not noise_indexes:
        noise_indexes = list(corrupted.index[:1])
    noise_ids = _paper_ids(corrupted, noise_indexes)
    noise_prefix = " ".join([NOISE] * 30)
    corrupted.loc[noise_indexes, "summary"] = corrupted.loc[
        noise_indexes, "summary"
    ].map(lambda value: f"{noise_prefix} {value}")
    scenarios.append(
        {
            "type": "inject_noise",
            "description": "Prefixed selected summaries with repeated synthetic noise.",
            "affected_rows": len(noise_ids),
            "paper_ids": noise_ids,
        }
    )

    truncate_count = max(1, min(5, len(corrupted)))
    truncate_indexes = list(corrupted.index[:truncate_count])
    truncate_ids = _paper_ids(corrupted, truncate_indexes)
    corrupted.loc[truncate_indexes, "title"] = corrupted.loc[
        truncate_indexes, "title"
    ].map(lambda value: str(value)[:7].strip())
    scenarios.append(
        {
            "type": "truncate_title",
            "description": "Truncated selected titles to fewer than 8 characters.",
            "affected_rows": len(truncate_ids),
            "paper_ids": truncate_ids,
        }
    )

    stale_count = max(1, ceil(len(corrupted) * 0.35))
    stale_indexes = list(corrupted.index[:stale_count])
    stale_ids = _paper_ids(corrupted, stale_indexes)
    stale_dates = pd.to_datetime(
        corrupted.loc[stale_indexes, "published"], errors="coerce", utc=True
    ) - pd.Timedelta(days=365)
    corrupted.loc[stale_indexes, "published"] = stale_dates.dt.strftime("%Y-%m-%d")
    corrupted.loc[stale_indexes, "age_days"] = (
        pd.to_numeric(corrupted.loc[stale_indexes, "age_days"], errors="coerce")
        + 365
    ).astype(int)
    scenarios.append(
        {
            "type": "stale_date",
            "description": "Moved selected publication dates 365 days into the past.",
            "affected_rows": len(stale_ids),
            "paper_ids": stale_ids,
        }
    )

    _rebuild_embedding_text(corrupted)

    duplicate_count = max(1, min(2, len(corrupted)))
    duplicates = corrupted.iloc[:duplicate_count].copy(deep=True)
    duplicate_ids = duplicates["paper_id"].astype(str).tolist()
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)
    scenarios.append(
        {
            "type": "duplicate_rows",
            "description": "Appended exact copies of selected records.",
            "affected_rows": duplicate_count,
            "paper_ids": duplicate_ids,
        }
    )

    log = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_rows": len(df),
        "output_rows": len(corrupted),
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }
    write_json(Path(output_log_path), log)
    return corrupted.reset_index(drop=True)
