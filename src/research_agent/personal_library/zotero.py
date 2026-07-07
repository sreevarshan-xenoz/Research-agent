"""
P28: Personal Research Library — Zotero Import

Supports importing from:
- Zotero API (via API key + user ID)
- CSL JSON exports (standard Zotero export format)
- BibTeX files
- RIS files
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx

from research_agent.personal_library.models import (
    LibraryEntry,
    LibraryItem,
    Author,
    ZoteroImportResult,
    LibraryEntryStatus,
    ReadingListStatus,
)

logger = logging.getLogger(__name__)


class ZoteroImporter:
    """Import papers from Zotero via API or file export."""

    def __init__(
        self,
        api_key: str | None = None,
        user_id: str | None = None,
        group_id: str | None = None,
    ):
        self.api_key = api_key or os.getenv("ZOTERO_API_KEY", "")
        self.user_id = user_id or os.getenv("ZOTERO_USER_ID", "")
        self.group_id = group_id or os.getenv("ZOTERO_GROUP_ID", "")
        self._client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "ResearchAgent/0.1 (research-agent)",
                "Zotero-API-Key": self.api_key or "",
            },
        )

    # ── Zotero API Import ────────────────────────────────────

    def import_from_api(
        self,
        limit: int = 50,
        offset: int = 0,
        collection_key: str | None = None,
    ) -> ZoteroImportResult:
        """Import entries from the Zotero API."""
        if not self.api_key or not self.user_id:
            return ZoteroImportResult(
                success=False,
                errors=["Zotero API key and User ID are required"],
            )

        base = f"https://api.zotero.org/users/{self.user_id}"
        if collection_key:
            url = f"{base}/collections/{collection_key}/items/top"
        else:
            url = f"{base}/items/top"

        params: dict[str, Any] = {
            "limit": str(min(limit, 100)),
            "start": str(offset),
            "itemType": "-attachment,-note",
            "sort": "dateAdded",
            "direction": "desc",
            "include": "bib,data,citation",
        }

        try:
            resp = self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            headers = resp.headers
            total_results = int(headers.get("Total-Results", 0))

            entries: list[LibraryEntry] = []
            errors: list[str] = []
            skipped = 0

            for item in data:
                try:
                    entry = self._parse_zotero_item(item)
                    if entry:
                        entries.append(entry)
                    else:
                        skipped += 1
                except Exception as exc:
                    errors.append(f"Failed to parse item: {exc}")
                    skipped += 1

            return ZoteroImportResult(
                success=True,
                entries_imported=len(entries),
                entries_skipped=skipped,
                entries=entries,
                errors=errors,
                warnings=[] if total_results > len(entries) else [],
            )

        except httpx.HTTPStatusError as exc:
            return ZoteroImportResult(
                success=False,
                errors=[f"Zotero API error: {exc.response.status_code} - {exc.response.text[:200]}"],
            )
        except Exception as exc:
            return ZoteroImportResult(
                success=False,
                errors=[f"Zotero import failed: {exc}"],
            )

    def _parse_zotero_item(self, item: dict[str, Any]) -> LibraryEntry | None:
        """Parse a single Zotero API item into a LibraryEntry."""
        data = item.get("data", {})
        item_type = data.get("itemType", "")
        if item_type in ("attachment", "note"):
            return None

        title = data.get("title", "")
        if not title:
            return None

        creators = data.get("creators", [])
        authors: list[Author] = []
        for c in creators:
            first = c.get("firstName", "")
            last = c.get("lastName", "")
            name = f"{first} {last}".strip()
            if name:
                authors.append(Author(name=name, first_name=first, last_name=last))

        # Extract DOI
        doi = data.get("DOI", "")
        # Extract URL
        url = data.get("url", "")
        # arXiv ID
        arxiv_id = ""
        extra = data.get("extra", "")
        arxiv_match = re.search(r"arxiv\s*:\s*(\d+\.\d+)", extra, re.IGNORECASE)
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)

        # Tags from Zotero
        tags = [t.get("tag", "") for t in data.get("tags", []) if t.get("tag")]

        # Date/year
        date = data.get("date", "")
        year = date[:4] if len(date) >= 4 and date[:4].isdigit() else ""

        # Venue
        venue = data.get("publicationTitle", "") or data.get("bookTitle", "") or data.get("publisher", "")

        # Abstract
        abstract = data.get("abstractNote", "")

        entry_id = f"zotero-{item.get('key', doi or title[:20])}"

        return LibraryEntry(
            entry_id=entry_id,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            venue=venue,
            url=url,
            doi=doi,
            arxiv_id=arxiv_id,
            tags=tags,
            status=LibraryEntryStatus.IMPORTED,
            reading_status=ReadingListStatus.TO_READ,
            source="zotero",
        )

    # ── CSL JSON Import ──────────────────────────────────────

    def import_from_csl_json(self, json_path: str | Path) -> ZoteroImportResult:
        """Import entries from a CSL JSON file (Zotero export format)."""
        path = Path(json_path)
        if not path.exists():
            return ZoteroImportResult(success=False, errors=[f"File not found: {path}"])

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = [data]
        except json.JSONDecodeError as exc:
            return ZoteroImportResult(success=False, errors=[f"Invalid JSON: {exc}"])

        entries: list[LibraryEntry] = []
        errors: list[str] = []
        skipped = 0

        for item in data:
            try:
                title = item.get("title", "")
                if not title:
                    skipped += 1
                    continue

                authors: list[Author] = []
                for c in item.get("author", []):
                    if isinstance(c, dict):
                        given = c.get("given", "")
                        family = c.get("family", "")
                        name = f"{given} {family}".strip()
                        if name:
                            authors.append(Author(name=name, first_name=given, last_name=family))
                    elif isinstance(c, str):
                        authors.append(Author(name=c))

                doi = item.get("DOI", "")
                url = item.get("URL", "")
                issued = item.get("issued", {})
                year = ""
                if isinstance(issued, dict):
                    date_parts = issued.get("date-parts", [[]])
                    if date_parts and date_parts[0]:
                        year = str(date_parts[0][0])
                elif isinstance(issued, list):
                    if issued and issued[0]:
                        year = str(issued[0])

                container = item.get("container-title", "")
                tags = [t.get("name", str(t)) for t in item.get("categories", []) if t]

                entry = LibraryEntry(
                    entry_id=f"csl-{doi or title[:30]}",
                    title=title,
                    authors=authors,
                    abstract=item.get("abstract", ""),
                    year=year,
                    venue=container,
                    url=url,
                    doi=doi,
                    tags=tags,
                    status=LibraryEntryStatus.IMPORTED,
                    reading_status=ReadingListStatus.TO_READ,
                    source="zotero",
                )
                entries.append(entry)

            except Exception as exc:
                errors.append(f"Failed to parse CSL item: {exc}")
                skipped += 1

        return ZoteroImportResult(
            success=True,
            entries_imported=len(entries),
            entries_skipped=skipped,
            entries=entries,
            errors=errors,
        )

    # ── BibTeX Import ────────────────────────────────────────

    def import_from_bibtex(self, bibtex_path: str | Path) -> ZoteroImportResult:
        """Import entries from a BibTeX file."""
        path = Path(bibtex_path)
        if not path.exists():
            return ZoteroImportResult(success=False, errors=[f"File not found: {path}"])

        try:
            bibtex_content = path.read_text(encoding="utf-8")
        except Exception as exc:
            return ZoteroImportResult(success=False, errors=[f"Failed to read file: {exc}"])

        return self.import_from_bibtex_string(bibtex_content)

    def import_from_bibtex_string(self, bibtex: str) -> ZoteroImportResult:
        """Import entries from a BibTeX string."""
        entries: list[LibraryEntry] = []
        errors: list[str] = []
        skipped = 0

        # Simple BibTeX parser
        entry_pattern = re.compile(
            r"@(\w+)\s*\{\s*([^,]+),\s*(.*?)\s*\}", re.DOTALL
        )
        field_pattern = re.compile(
            r"(\w+)\s*=\s*\{([^}]*)\}", re.DOTALL
        )

        for match in entry_pattern.finditer(bibtex):
            try:
                cite_key = match.group(2).strip()
                body = match.group(3)

                fields: dict[str, str] = {}
                for f_match in field_pattern.finditer(body):
                    key = f_match.group(1).lower()
                    value = f_match.group(2).strip()
                    fields[key] = value

                title = fields.get("title", "")
                if not title:
                    skipped += 1
                    continue

                authors_str = fields.get("author", "")
                authors: list[Author] = []
                if authors_str:
                    for a in re.split(r"\s+and\s+", authors_str):
                        a = a.strip()
                        if a:
                            parts = a.split(", ")
                            if len(parts) == 2:
                                authors.append(Author(name=a, last_name=parts[0], first_name=parts[1]))
                            else:
                                authors.append(Author(name=a))

                year = fields.get("year", "")
                doi = fields.get("doi", "")
                url = fields.get("url", "")
                venue = fields.get("journal", "") or fields.get("booktitle", "") or fields.get("publisher", "")
                abstract = fields.get("abstract", "")
                tags_raw = fields.get("keywords", "")
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

                entry_id = f"bib-{doi or cite_key or title[:30]}"

                entry = LibraryEntry(
                    entry_id=entry_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    venue=venue,
                    url=url,
                    doi=doi,
                    bibtex=match.group(0)[:500],  # store first 500 chars of bibtex entry
                    tags=tags,
                    status=LibraryEntryStatus.IMPORTED,
                    reading_status=ReadingListStatus.TO_READ,
                    source="zotero",
                )
                entries.append(entry)

            except Exception as exc:
                errors.append(f"Failed to parse BibTeX entry '{cite_key}': {exc}")
                skipped += 1

        return ZoteroImportResult(
            success=True,
            entries_imported=len(entries),
            entries_skipped=skipped,
            entries=entries,
            errors=errors,
        )

    # ── Health Check ─────────────────────────────────────────

    def check_connection(self) -> dict[str, Any]:
        """Check if Zotero API credentials are working."""
        if not self.api_key or not self.user_id:
            return {"configured": False, "message": "Zotero API key or User ID not configured"}

        try:
            url = f"https://api.zotero.org/users/{self.user_id}/items/top?limit=1"
            resp = self._client.get(url)
            if resp.status_code == 200:
                total = int(resp.headers.get("Total-Results", 0))
                return {
                    "configured": True,
                    "connected": True,
                    "total_items": total,
                    "message": f"Connected. {total} items in library.",
                }
            elif resp.status_code == 403:
                return {"configured": True, "connected": False, "message": "Invalid API key or insufficient permissions"}
            else:
                return {
                    "configured": True,
                    "connected": False,
                    "message": f"HTTP {resp.status_code}: {resp.text[:100]}",
                }
        except Exception as exc:
            return {"configured": True, "connected": False, "message": f"Connection error: {exc}"}

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


# ── Standalone convenience functions (used by routes.py) ────────────────────


def _entry_to_library_item(entry: LibraryEntry) -> LibraryItem:
    """Convert a LibraryEntry dataclass to a LibraryItem Pydantic model."""
    return LibraryItem(
        id=entry.entry_id,
        title=entry.title,
        authors=[a.name for a in entry.authors],
        abstract=entry.abstract,
        published_at=entry.year,
        year=entry.year,
        venue=entry.venue,
        url=entry.url,
        doi=entry.doi,
        arxiv_id=entry.arxiv_id,
        pdf_path=entry.pdf_path,
        bibtex=entry.bibtex,
        tags=entry.tags,
        collections=entry.collections,
        kind=entry.source,
        source=entry.source,
        notes=entry.notes,
        imported_at=entry.imported_at,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def import_from_bibtex(content: str) -> list[LibraryItem]:
    """Parse a BibTeX string and return a list of LibraryItem objects."""
    importer = ZoteroImporter()
    result = importer.import_from_bibtex_string(content)
    return [_entry_to_library_item(e) for e in result.entries]


def import_from_zotero_json(content: str) -> list[LibraryItem]:
    """Parse a Zotero CSL JSON string and return a list of LibraryItem objects."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        data = [data]

    items: list[LibraryItem] = []
    for citem in data:
        title = citem.get("title", "")
        if not title:
            continue
        authors: list[str] = []
        for c in citem.get("author", []):
            if isinstance(c, dict):
                given = c.get("given", "")
                family = c.get("family", "")
                name = f"{given} {family}".strip()
                if name:
                    authors.append(name)
            elif isinstance(c, str):
                authors.append(c)
        doi = citem.get("DOI", "")
        url = citem.get("URL", "")
        issued = citem.get("issued", {})
        year = ""
        if isinstance(issued, dict):
            date_parts = issued.get("date-parts", [[]])
            if date_parts and date_parts[0]:
                year = str(date_parts[0][0])
        elif isinstance(issued, list):
            if issued and issued[0]:
                year = str(issued[0])
        container = citem.get("container-title", "")
        tags_list = [t.get("name", str(t)) for t in citem.get("categories", []) if t]
        items.append(LibraryItem(
            id=f"csl-{doi or title[:30]}",
            title=title,
            authors=authors,
            abstract=citem.get("abstract", ""),
            year=year,
            venue=container,
            url=url,
            doi=doi,
            tags=tags_list,
            kind="article",
            source="zotero",
        ))
    return items
