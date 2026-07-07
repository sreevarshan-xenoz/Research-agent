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


def generate_bibtex_string(item: LibraryItem) -> str:
    """Generate a BibTeX entry string from a LibraryItem's metadata.

    Uses the stored bibtex field if available, otherwise generates
    a BibTeX entry from the item's metadata fields.
    """
    # Use stored bibtex if available
    if item.bibtex and len(item.bibtex) > 20:
        return item.bibtex

    # Determine entry type based on kind
    kind_map = {
        "article": "article",
        "book": "book",
        "thesis": "phdthesis",
        "conference": "inproceedings",
        "report": "techreport",
        "manual": "misc",
    }
    entry_type = kind_map.get(item.kind or "article", "misc")

    # Build cite key
    first_author = ""
    if item.authors:
        first = item.authors[0]
        parts = first.split(", ")
        if len(parts) == 2:
            first_author = parts[0]
        else:
            last_part = first.split()[-1] if first.split() else ""
            first_author = last_part
    year_str = (item.year or item.published_at or "")[:4]
    cite_key = first_author.lower() if first_author else "unknown"
    if year_str:
        cite_key += year_str
    if item.doi:
        cite_key += re.sub(r"[^a-zA-Z0-9]", "", item.doi[:8])
    cite_key = re.sub(r"[^a-zA-Z0-9_-]", "", cite_key) or "ref"

    lines = [f"@{entry_type}{{{cite_key},"]
    _add_bibtex_field(lines, "title", item.title)
    _add_bibtex_field(lines, "author", " and ".join(item.authors) if item.authors else "")
    _add_bibtex_field(lines, "abstract", item.abstract)
    _add_bibtex_field(lines, "year", year_str)
    _add_bibtex_field(lines, "doi", item.doi)
    _add_bibtex_field(lines, "url", item.url)
    _add_bibtex_field(lines, "journal", item.venue if item.kind == "article" else "")
    _add_bibtex_field(lines, "booktitle", item.venue if item.kind == "conference" else "")
    _add_bibtex_field(lines, "publisher", item.venue if item.kind == "book" else "")
    if item.arxiv_id:
        _add_bibtex_field(lines, "archivePrefix", "arXiv")
        _add_bibtex_field(lines, "eprint", item.arxiv_id)
    if item.tags:
        _add_bibtex_field(lines, "keywords", ", ".join(item.tags))
    lines.append("}")

    return "\n".join(lines)


def _add_bibtex_field(lines: list[str], key: str, value: str) -> None:
    """Add a BibTeX field line if value is non-empty."""
    if not value or not value.strip():
        return
    # Escape special BibTeX characters
    escaped = value.replace("}", "\}").replace("{", "\{")
    escaped = escaped.replace("\&", "\\&")
    lines.append(f"  {key} = {{{escaped}}},")


def generate_ris_string(item: LibraryItem) -> str:
    """Generate a RIS format entry string from a LibraryItem's metadata."""
    lines = []

    # Determine RIS type
    type_map = {
        "article": "JOUR",
        "book": "BOOK",
        "thesis": "THES",
        "conference": "CONF",
        "report": "RPRT",
        "manual": "GEN",
    }
    ris_type = type_map.get(item.kind or "article", "JOUR")
    lines.append(f"TY  - {ris_type}")

    if item.title:
        lines.append(f"TI  - {item.title}")

    if item.authors:
        for author in item.authors:
            lines.append(f"AU  - {author}")

    year_str = (item.year or item.published_at or "")[:4]
    if year_str:
        lines.append(f"PY  - {year_str}//")

    if item.doi:
        lines.append(f"DO  - {item.doi}")

    if item.url:
        lines.append(f"UR  - {item.url}")

    if item.abstract:
        lines.append(f"AB  - {item.abstract}")

    if item.tags:
        for tag in item.tags:
            lines.append(f"KW  - {tag}")

    if item.venue:
        if ris_type == "JOUR":
            lines.append(f"JF  - {item.venue}")
        elif ris_type == "CONF":
            lines.append(f"T2  - {item.venue}")
        else:
            lines.append(f"PB  - {item.venue}")

    if item.arxiv_id:
        lines.append(f"ID  - arXiv:{item.arxiv_id}")

    lines.append("ER  - ")

    return "\n".join(lines)


def generate_csl_json_string(item: LibraryItem) -> str:
    """Generate a CSL JSON entry string from a LibraryItem's metadata."""
    type_map = {
        "article": "article-journal",
        "book": "book",
        "thesis": "thesis",
        "conference": "paper-conference",
        "report": "report",
        "manual": "article",
    }
    csl_type = type_map.get(item.kind or "article", "article")

    csl: dict[str, Any] = {
        "id": item.id or "",
        "type": csl_type,
        "title": item.title or "",
    }

    if item.authors:
        csl["author"] = []
        for author_str in item.authors:
            parts = author_str.split(", ")
            if len(parts) == 2:
                csl["author"].append({
                    "family": parts[0],
                    "given": parts[1],
                })
            else:
                name_parts = author_str.split()
                if len(name_parts) >= 2:
                    csl["author"].append({
                        "family": name_parts[-1],
                        "given": " ".join(name_parts[:-1]),
                    })
                else:
                    csl["author"].append({"literal": author_str})

    year_str = (item.year or item.published_at or "")[:4]
    if year_str:
        csl["issued"] = {"date-parts": [[int(year_str)]]}

    if item.doi:
        csl["DOI"] = item.doi

    if item.url:
        csl["URL"] = item.url

    if item.abstract:
        csl["abstract"] = item.abstract

    if item.venue:
        if csl_type in ("article-journal", "article-magazine"):
            csl["container-title"] = item.venue
        elif csl_type == "paper-conference":
            csl["container-title"] = item.venue
        elif csl_type == "book":
            csl["publisher"] = item.venue
        else:
            csl["publisher"] = item.venue

    if item.tags:
        csl["categories"] = item.tags

    if item.notes:
        csl["note"] = item.notes

    if item.arxiv_id:
        csl["archive"] = "arXiv"
        csl["archive_location"] = item.arxiv_id

    return json.dumps(csl, indent=2, ensure_ascii=False)


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
