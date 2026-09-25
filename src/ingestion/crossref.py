from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Convert a Crossref work-list response into the pipeline's stable schema."""
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        paper_id = normalize_whitespace(str(item.get("DOI", ""))).lower()
        title = normalize_whitespace(_first_text(item.get("title")))
        summary = _strip_markup(_first_text(item.get("abstract")))
        if not paper_id or not title or not summary:
            continue

        authors = []
        for author in item.get("author", []) or []:
            name = normalize_whitespace(
                " ".join(str(author.get(part, "")) for part in ("given", "family"))
            )
            if name:
                authors.append(name)

        categories = [
            normalize_whitespace(str(subject))
            for subject in (item.get("subject", []) or [])
            if normalize_whitespace(str(subject))
        ]
        published = _crossref_date(item.get("published"))
        updated = _crossref_datetime(item.get("created")) or published
        if not published:
            continue

        url = normalize_whitespace(str(item.get("URL", ""))) or f"https://doi.org/{paper_id}"
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "Uncategorized",
                published=published,
                updated=updated,
                abs_url=url,
                pdf_url=url,
                comment=f"Crossref record {paper_id}",
            )
        )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref when explicitly requested, otherwise use the committed snapshot.

    The local snapshot is deliberately the default: it makes the lab reproducible and
    remains available when Crossref rate-limits the request or the network is down.
    """
    payload: dict | None = None
    if settings.refresh_source:
        try:
            response = requests.get(
                "https://api.crossref.org/works",
                params={
                    "query": settings.source_query,
                    "filter": settings.source_filter,
                    "rows": settings.max_results,
                },
                headers={"User-Agent": "day10-data-pipeline-lab/0.1"},
                timeout=20,
            )
            # 429 and 503 intentionally fall through to the offline snapshot.
            response.raise_for_status()
            payload = response.json()
            write_json(settings.paths.raw_api_response, payload)
        except (requests.RequestException, ValueError):
            payload = None

    if payload is None:
        payload = read_json(settings.paths.raw_api_response)

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load the parsed raw artifact into typed records."""
    return [PaperRecord(**item) for item in read_json(path)]


def _first_text(value: object) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _strip_markup(value: str) -> str:
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", value))


def _crossref_date(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts", [[]])
    if not parts or not parts[0]:
        return ""
    values = list(parts[0]) + [1, 1]
    try:
        return date(int(values[0]), int(values[1]), int(values[2])).isoformat()
    except (TypeError, ValueError):
        return ""


def _crossref_datetime(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    date_time = str(value.get("date-time", ""))
    return date_time[:10] if len(date_time) >= 10 else ""
