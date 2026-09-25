from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean parsed records and create the canonical embedding document."""
    rows = []
    for record in records:
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        paper_id = normalize_whitespace(record.paper_id).lower()
        authors = [normalize_whitespace(author) for author in record.authors if normalize_whitespace(author)]
        categories = [
            normalize_whitespace(category)
            for category in record.categories
            if normalize_whitespace(category)
        ]
        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": normalize_whitespace(record.primary_category),
                "published": record.published,
                "updated": record.updated,
                "abs_url": record.abs_url,
                "pdf_url": record.pdf_url,
                "comment": record.comment,
            }
        )

    columns = [
        "paper_id", "title", "summary", "authors", "categories", "primary_category",
        "published", "updated", "abs_url", "pdf_url", "comment", "authors_joined",
        "categories_joined", "summary_chars", "age_days", "text_for_embedding",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)
    df["published"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
    df["updated"] = pd.to_datetime(df["updated"], errors="coerce", utc=True)
    df = df.dropna(subset=["paper_id", "title", "summary", "published"])
    df = df[(df["paper_id"] != "") & (df["title"] != "") & (df["summary"] != "")]
    df = df.drop_duplicates(subset="paper_id", keep="first").copy()

    run_timestamp = pd.Timestamp(run_date)
    if run_timestamp.tzinfo is None:
        run_timestamp = run_timestamp.tz_localize(UTC)
    else:
        run_timestamp = run_timestamp.tz_convert(UTC)
    df["age_days"] = (run_timestamp.normalize() - df["published"].dt.normalize()).dt.days
    df["authors_joined"] = df["authors"].apply(lambda values: ", ".join(values))
    df["categories_joined"] = df["categories"].apply(lambda values: ", ".join(values))
    df["summary_chars"] = df["summary"].str.len()
    df["published"] = df["published"].dt.strftime("%Y-%m-%d")
    df["updated"] = df["updated"].dt.strftime("%Y-%m-%d").fillna("")
    df["text_for_embedding"] = df.apply(
        lambda row: (
            f"Title: {row['title']}\n"
            f"Authors: {row['authors_joined']}\n"
            f"Published: {row['published']}\n"
            f"Categories: {row['categories_joined']}\n"
            f"Summary: {row['summary']}"
        ),
        axis=1,
    )
    return df.sort_values("paper_id").reset_index(drop=True)[columns]
