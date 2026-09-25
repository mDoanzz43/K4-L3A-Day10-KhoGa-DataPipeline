from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from typing import Any, Iterable

import pandas as pd

from ingestion.crossref import PaperRecord


OUTPUT_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "age_days",
    "text_for_embedding",
]


def _clean_text(value: Any) -> str:
    """Remove markup, decode entities, and collapse all whitespace."""
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]*>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_list(values: Any) -> list[str]:
    """Normalize a list while preserving order and removing duplicates."""
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, Iterable) or isinstance(values, (dict, bytes)):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean_text(value)
        key = item.casefold()
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
    return cleaned


def _normalize_paper_id(value: Any) -> str:
    paper_id = _clean_text(value)
    paper_id = re.sub(
        r"^(?:https?://)?(?:dx\.)?doi\.org/", "", paper_id, flags=re.IGNORECASE
    )
    paper_id = re.sub(r"^doi\s*:\s*", "", paper_id, flags=re.IGNORECASE)
    return paper_id.strip().lower()


def _parse_date(value: Any) -> pd.Timestamp | None:
    """Parse a date-like value as UTC, returning midnight for its date."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
    except (TypeError, ValueError, OverflowError):
        return None
    if pd.isna(parsed) or not isinstance(parsed, pd.Timestamp):
        return None
    return parsed.normalize()


def _normalize_run_date(run_date: datetime) -> pd.Timestamp:
    if not isinstance(run_date, datetime):
        raise TypeError("run_date must be a datetime")
    timestamp = pd.Timestamp(run_date)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(UTC)
    else:
        timestamp = timestamp.tz_convert(UTC)
    return timestamp.normalize()


def _embedding_text(row: dict[str, Any]) -> str:
    return "\n".join(
        (
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        )
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Build the normalized dataframe consumed by quality and embedding steps.

    Records without a usable paper ID, title, or publication date are excluded.
    Duplicate IDs are resolved deterministically by keeping their first record.
    """
    run_day = _normalize_run_date(run_date)
    rows: list[dict[str, Any]] = []

    for record in records:
        paper_id = _normalize_paper_id(record.paper_id)
        title = _clean_text(record.title)
        published_at = _parse_date(record.published)
        if not paper_id or not title or published_at is None:
            continue

        authors = _clean_list(record.authors)
        categories = _clean_list(record.categories)
        summary = _clean_text(record.summary)
        published = published_at.date().isoformat()
        updated_at = _parse_date(record.updated)
        normalized_updated = updated_at if updated_at is not None else published_at

        row: dict[str, Any] = {
            "paper_id": paper_id,
            "title": title,
            "summary": summary,
            "authors": authors,
            "categories": categories,
            "primary_category": _clean_text(record.primary_category)
            or (categories[0] if categories else ""),
            "published": published,
            "updated": normalized_updated.date().isoformat(),
            "abs_url": _clean_text(record.abs_url),
            "pdf_url": _clean_text(record.pdf_url),
            "comment": _clean_text(record.comment),
            "authors_joined": ", ".join(authors),
            "categories_joined": ", ".join(categories),
            "summary_chars": len(summary),
            "age_days": int((run_day - published_at).days),
        }
        row["text_for_embedding"] = _embedding_text(row)
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    dataframe = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    dataframe = dataframe.drop_duplicates(subset=["paper_id"], keep="first")
    dataframe = dataframe.sort_values(
        by=["published", "paper_id"], ascending=[False, True], kind="stable"
    )
    return dataframe.reset_index(drop=True)
