from __future__ import annotations

import html
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import requests

from core.config import Settings

LOGGER = logging.getLogger(__name__)
CROSSREF_WORKS_URL = "https://api.crossref.org/works"


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


def _clean_text(value: Any) -> str:
    """Remove HTML/JATS markup and collapse whitespace."""
    if value is None:
        return ""

    text = html.unescape(str(value))
    # Crossref abstracts commonly contain namespaced JATS tags such as
    # <jats:p> and <jats:italic>. Spaces keep adjacent elements separated.
    text = re.sub(r"<[^>]*>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_doi(value: Any) -> str:
    """Return a canonical, lower-case DOI without URL/``doi:`` prefixes."""
    doi = _clean_text(value)
    doi = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi\s*:\s*", "", doi, flags=re.IGNORECASE)
    return doi.strip().lower()


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        value = next((entry for entry in value if entry), "")
    return _clean_text(value)


def _extract_authors(item: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    raw_authors = item.get("author") or []
    if not isinstance(raw_authors, list):
        return authors

    for author in raw_authors:
        if not isinstance(author, dict):
            continue
        name = _clean_text(
            " ".join(
                part
                for part in (
                    _clean_text(author.get("given")),
                    _clean_text(author.get("family")),
                )
                if part
            )
        )
        # Some Crossref records represent an organization as an author.
        name = name or _clean_text(author.get("name"))
        if name:
            authors.append(name)
    return authors


def _extract_categories(item: dict[str, Any]) -> list[str]:
    subjects = item.get("subject") or []
    if isinstance(subjects, str):
        subjects = [subjects]
    if not isinstance(subjects, list):
        return []

    categories: list[str] = []
    for subject in subjects:
        category = _clean_text(subject)
        if category and category not in categories:
            categories.append(category)
    return categories


def _iso_date_from_block(block: Any) -> str:
    """Convert a Crossref date block to an ISO-8601 calendar date."""
    if not isinstance(block, dict):
        return ""

    date_parts = block.get("date-parts")
    if isinstance(date_parts, list) and date_parts:
        parts = date_parts[0]
        if isinstance(parts, list) and parts:
            try:
                year = int(parts[0])
                month = int(parts[1]) if len(parts) > 1 else 1
                day = int(parts[2]) if len(parts) > 2 else 1
                return date(year, month, day).isoformat()
            except (TypeError, ValueError, OverflowError):
                pass

    # ``created``, ``deposited`` and ``indexed`` often expose date-time
    # instead of date-parts. Normalize Z so datetime.fromisoformat accepts it.
    date_time = block.get("date-time")
    if isinstance(date_time, str) and date_time.strip():
        try:
            parsed = datetime.fromisoformat(date_time.strip())
            return parsed.date().isoformat()
        except ValueError:
            pass

    timestamp = block.get("timestamp")
    if isinstance(timestamp, (int, float)):
        try:
            return datetime.fromtimestamp(timestamp / 1000, tz=UTC).date().isoformat()
        except (ValueError, OSError, OverflowError):
            pass
    return ""


def _extract_date(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        result = _iso_date_from_block(item.get(key))
        if result:
            return result
    return ""


def _extract_pdf_url(item: dict[str, Any]) -> str:
    links = item.get("link") or []
    if not isinstance(links, list):
        return ""
    for link in links:
        if not isinstance(link, dict):
            continue
        content_type = str(link.get("content-type") or "").lower()
        if content_type == "application/pdf":
            return _clean_text(link.get("URL"))
    return ""


def parse_crossref_payload(payload: dict[str, Any]) -> list[PaperRecord]:
    """Parse a Crossref ``works`` response into normalized paper records."""
    message = payload.get("message") if isinstance(payload, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        return []

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        doi = _normalize_doi(item.get("DOI"))
        title = _first_text(item.get("title"))
        if not doi or not title:
            continue

        categories = _extract_categories(item)
        published = _extract_date(
            item,
            ("published-print", "published-online", "published", "issued", "created"),
        )
        updated = _extract_date(item, ("updated", "deposited", "indexed")) or published
        abs_url = _clean_text(item.get("URL")) or f"https://doi.org/{doi}"

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=_clean_text(item.get("abstract")),
                authors=_extract_authors(item),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=_extract_pdf_url(item),
                comment=_clean_text(item.get("comment")),
            )
        )
    return records


def _request_with_retry(
    url: str,
    params: dict[str, Any],
    max_retries: int = 3,
    backoff: float = 1.0,
) -> dict[str, Any]:
    """Fetch JSON from Crossref, retrying transient 429/503 failures."""
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code in (429, 503):
                last_error = requests.HTTPError(
                    f"Crossref returned HTTP {response.status_code}", response=response
                )
            else:
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Crossref response must be a JSON object")
                return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc

        if attempt < max_retries - 1:
            time.sleep(backoff * (2**attempt))

    raise RuntimeError(
        f"Failed to fetch {url} after {max_retries} attempts"
    ) from last_error


def _read_payload_snapshot(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Crossref offline snapshot not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise TypeError(f"Crossref snapshot must contain a JSON object: {path}")
    return payload


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref records, falling back to the checked-in raw snapshot.

    A successful live response replaces ``raw_api_response``. If Crossref is
    unavailable, rate-limits the request, or returns invalid JSON, the existing
    snapshot remains untouched and is used to keep the pipeline operational.
    """
    configured_url = getattr(settings, "source_url", None) or CROSSREF_WORKS_URL
    base_url = str(configured_url).rstrip("/")
    url = base_url if base_url.endswith("/works") else f"{base_url}/works"
    params: dict[str, Any] = {
        "query": settings.source_query,
        "rows": settings.max_results,
    }
    if settings.source_filter:
        params["filter"] = settings.source_filter

    raw_path = Path(settings.paths.raw_api_response)
    try:
        payload = _request_with_retry(url, params)
    except (RuntimeError, requests.RequestException) as exc:
        LOGGER.warning(
            "Crossref API unavailable; using offline snapshot %s (%s)", raw_path, exc
        )
        try:
            payload = _read_payload_snapshot(raw_path)
        except (OSError, ValueError) as snapshot_error:
            raise RuntimeError(
                "Crossref API failed and no valid offline snapshot is available "
                f"at {raw_path}"
            ) from snapshot_error
    else:
        _write_json(raw_path, payload)

    records = parse_crossref_payload(payload)
    serialized_records = [asdict(record) for record in records]
    _write_json(Path(settings.paths.raw_records_json), serialized_records)
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load serialized ``PaperRecord`` objects from a raw JSON artifact."""
    path = Path(path)
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    # Also accept a Crossref response snapshot for convenient recovery.
    if isinstance(data, dict):
        return parse_crossref_payload(data)
    if not isinstance(data, list):
        raise TypeError(f"Raw records must contain a JSON list: {path}")

    records: list[PaperRecord] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw_authors = item.get("authors") or []
        raw_categories = item.get("categories") or []
        authors = raw_authors if isinstance(raw_authors, list) else []
        categories = raw_categories if isinstance(raw_categories, list) else []
        records.append(
            PaperRecord(
                paper_id=_normalize_doi(item.get("paper_id")),
                title=_clean_text(item.get("title")),
                summary=_clean_text(item.get("summary")),
                authors=[
                    _clean_text(value) for value in authors if _clean_text(value)
                ],
                categories=[
                    _clean_text(value) for value in categories if _clean_text(value)
                ],
                primary_category=_clean_text(item.get("primary_category")),
                published=_clean_text(item.get("published")),
                updated=_clean_text(item.get("updated")),
                abs_url=_clean_text(item.get("abs_url")),
                pdf_url=_clean_text(item.get("pdf_url")),
                comment=_clean_text(item.get("comment")),
            )
        )
    return records
