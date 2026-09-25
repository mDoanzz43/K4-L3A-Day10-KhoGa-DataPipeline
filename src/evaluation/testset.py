from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json


@dataclass(frozen=True)
class TestSet:
    """Serializable benchmark samples used to evaluate retrieval and QA."""

    samples: list[dict[str, Any]]


_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "published",
    "categories_joined",
}


def _value(row: pd.Series, column: str) -> str:
    value = row[column]
    if pd.isna(value):
        raise ValueError(f"Cleaned paper '{row['paper_id']}' has no value for '{column}'.")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Cleaned paper '{row['paper_id']}' has an empty value for '{column}'.")
    return text


def _sample(sample_id: str, question_type: str, question: str, ground_truth: str, doc_ids: list[str]) -> dict[str, Any]:
    """Create a sample compatible with both the current and legacy evaluators."""
    return {
        "id": sample_id,
        "type": question_type,
        "question_type": question_type,
        "question": question,
        "ground_truth": ground_truth,
        "ground_truth_doc_ids": doc_ids,
    }


def build_test_set(df: pd.DataFrame, output_path: Path) -> list[dict[str, Any]]:
    """Build ten deterministic benchmark questions from actual cleaned papers."""
    missing_columns = _REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"Cleaned dataframe is missing required columns: {sorted(missing_columns)}")
    if len(df) < 2:
        raise ValueError("At least two cleaned papers are required to create the multi-hop benchmark.")

    papers = df.reset_index(drop=True)
    samples: list[dict[str, Any]] = []
    sample_number = 1

    for offset in range(2):
        paper = papers.iloc[offset % len(papers)]
        title = _value(paper, "title")
        samples.append(
            _sample(
                f"eval_{sample_number:03d}",
                "summary",
                f"What is the main research summary of the paper '{title}'?",
                first_sentence(_value(paper, "summary")),
                [_value(paper, "paper_id")],
            )
        )
        sample_number += 1

    for offset in range(2, 4):
        paper = papers.iloc[offset % len(papers)]
        title = _value(paper, "title")
        samples.append(
            _sample(
                f"eval_{sample_number:03d}",
                "authors",
                f"Who authored the research paper '{title}'?",
                _value(paper, "authors_joined"),
                [_value(paper, "paper_id")],
            )
        )
        sample_number += 1

    for offset in range(4, 6):
        paper = papers.iloc[offset % len(papers)]
        title = _value(paper, "title")
        samples.append(
            _sample(
                f"eval_{sample_number:03d}",
                "date",
                f"When was the paper '{title}' published?",
                _value(paper, "published"),
                [_value(paper, "paper_id")],
            )
        )
        sample_number += 1

    for offset in range(6, 8):
        paper = papers.iloc[offset % len(papers)]
        title = _value(paper, "title")
        samples.append(
            _sample(
                f"eval_{sample_number:03d}",
                "category",
                f"What categories does the paper '{title}' belong to?",
                _value(paper, "categories_joined"),
                [_value(paper, "paper_id")],
            )
        )
        sample_number += 1

    for first_offset, second_offset in ((8, 9), (10, 11)):
        first_paper = papers.iloc[first_offset % len(papers)]
        second_paper = papers.iloc[second_offset % len(papers)]
        first_title = _value(first_paper, "title")
        second_title = _value(second_paper, "title")
        samples.append(
            _sample(
                f"eval_{sample_number:03d}",
                "multi_hop",
                f"How do the research topics in '{first_title}' and '{second_title}' relate to each other?",
                f"'{first_title}' studies {first_sentence(_value(first_paper, 'summary'))} "
                f"'{second_title}' studies {first_sentence(_value(second_paper, 'summary'))}",
                [_value(first_paper, "paper_id"), _value(second_paper, "paper_id")],
            )
        )
        sample_number += 1
    write_json(Path(output_path), samples)
    return samples


def load_or_create_test_set(df: pd.DataFrame, output_path: Path) -> TestSet:
    """Load an existing valid benchmark or create it from the supplied clean data."""
    path = Path(output_path)
    if path.exists():
        samples = read_json(path)
        if isinstance(samples, list) and len(samples) == 10:
            required_fields = {"id", "type", "question", "ground_truth", "ground_truth_doc_ids"}
            if all(required_fields <= set(sample) for sample in samples if isinstance(sample, dict)):
                return TestSet(samples=samples)
    return TestSet(samples=build_test_set(df, path))
