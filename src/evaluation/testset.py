from __future__ import annotations

from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, read_json, write_json


@dataclass(frozen=True)
class TestSet:
    """Serializable benchmark samples used to evaluate retrieval and QA."""

    samples: list[dict[str, Any]]

QUESTION_TYPES = (
    "summary",
    "authors",
    "date",
    "categories",
    "summary",
    "authors",
    "date",
    "categories",
    "summary",
    "authors",
)

REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "published",
}


def _text(value: Any) -> str:
    """Normalize scalar dataframe values and safely handle missing values."""
    if value is None or (not isinstance(value, (list, tuple)) and pd.isna(value)):
        return ""
    return normalize_whitespace(str(value))


def _joined_value(row: pd.Series, joined_column: str, list_column: str) -> str:
    joined = _text(row.get(joined_column))
    if joined:
        return joined

    values = row.get(list_column, [])
    if isinstance(values, (list, tuple)):
        return ", ".join(filter(None, (_text(value) for value in values)))
    return _text(values)


def _published_date(value: Any) -> str:
    published = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(published):
        return "Publication date unavailable."
    return published.date().isoformat()


def _build_question(row: pd.Series, question_type: str) -> tuple[str, str]:
    title = _text(row["title"])

    if question_type == "summary":
        return (
            f"What is the summary of the paper '{title}'?",
            first_sentence(_text(row["summary"])),
        )
    if question_type == "authors":
        authors = _joined_value(row, "authors_joined", "authors")
        return (
            f"Who authored the paper '{title}'?",
            authors or "No authors listed.",
        )
    if question_type == "date":
        return (
            f"When was the paper '{title}' published?",
            _published_date(row["published"]),
        )

    categories = _joined_value(row, "categories_joined", "categories")
    return (
        f"What categories are listed for the paper '{title}'?",
        categories or "No categories listed.",
    )


def build_test_set(df: pd.DataFrame, output_path: str | Path) -> list[dict[str, Any]]:
    """Build a deterministic ten-question benchmark from cleaned paper data."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    candidates = df.copy()
    candidates["paper_id"] = candidates["paper_id"].map(_text)
    candidates["title"] = candidates["title"].map(_text)
    candidates = candidates.loc[
        candidates["paper_id"].ne("") & candidates["title"].ne("")
    ].drop_duplicates(subset="paper_id", keep="first")

    if len(candidates) < 4:
        raise ValueError("At least 4 valid, uniquely identified papers are required")

    # Ten unique papers are preferred. For small valid datasets, cycling keeps the
    # public contract of ten questions while still covering all four task types.
    selected_rows = list(candidates.head(10).iterrows())
    row_cycle = cycle(row for _, row in selected_rows)

    test_set: list[dict[str, Any]] = []
    for number, question_type in enumerate(QUESTION_TYPES, start=1):
        row = next(row_cycle)
        question, ground_truth = _build_question(row, question_type)
        test_set.append(
            {
                "id": f"eval_{number:03d}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    write_json(Path(output_path), test_set)
    return test_set


def load_or_create_test_set(df: pd.DataFrame, output_path: str | Path) -> TestSet:
    """Load an existing valid benchmark or create it from clean data."""
    path = Path(output_path)
    if path.exists():
        samples = read_json(path)
        required_fields = {
            "id",
            "question_type",
            "question",
            "ground_truth",
            "ground_truth_doc_ids",
        }
        if (
            isinstance(samples, list)
            and len(samples) == 10
            and all(
                isinstance(sample, dict) and required_fields <= set(sample)
                for sample in samples
            )
        ):
            return TestSet(samples=samples)
    return TestSet(samples=build_test_set(df, path))
