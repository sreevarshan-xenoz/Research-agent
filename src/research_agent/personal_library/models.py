"""
P28: Personal Research Library — Data Models

Includes both dataclass models (for internal storage) and Pydantic models
(for API serialisation / route input validation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LibraryEntryStatus(str, Enum):
    """Status of a library entry in the research library."""
    IMPORTED = "imported"
    INDEXED = "indexed"
    ANNOTATED = "annotated"
    ARCHIVED = "archived"


class ReadingListStatus(str, Enum):
    """Reading progress status."""
    TO_READ = "to_read"
    READING = "reading"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class AnnotationType(str, Enum):
    """Type of annotation on a PDF/document."""
    HIGHLIGHT = "highlight"
    NOTE = "note"
    COMMENT = "comment"
    QUESTION = "question"


@dataclass
class TagSuggestion:
    """An auto-generated tag suggestion with confidence score."""
    tag: str
    confidence: float = 0.0
    source: str = "auto"  # "auto", "manual", "zotero"

    def to_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "confidence": round(self.confidence, 3), "source": self.source}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TagSuggestion:
        return cls(tag=data["tag"], confidence=data.get("confidence", 0.0), source=data.get("source", "auto"))


@dataclass
class Author:
    name: str
    first_name: str = ""
    last_name: str = ""
    orcid: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "first_name": self.first_name, "last_name": self.last_name, "orcid": self.orcid}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Author:
        return cls(
            name=data.get("name", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            orcid=data.get("orcid", ""),
        )


@dataclass
class Annotation:
    """A single annotation on a document (highlight, note, etc.)."""
    annotation_id: str
    entry_id: str
    annotation_type: AnnotationType = AnnotationType.NOTE
    text: str = ""
    page_number: int = 0
    color: str = "#ffeb3b"  # Default highlight color
    position: dict[str, float] = field(default_factory=dict)  # x, y, width, height on page
    created_at: str = ""
    updated_at: str = ""
    tags: list[str] = field(default_factory=list)
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "annotation_id": self.annotation_id,
            "entry_id": self.entry_id,
            "annotation_type": self.annotation_type.value,
            "text": self.text,
            "page_number": self.page_number,
            "color": self.color,
            "position": self.position,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "resolved": self.resolved,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Annotation:
        return cls(
            annotation_id=data["annotation_id"],
            entry_id=data["entry_id"],
            annotation_type=AnnotationType(data.get("annotation_type", "note")),
            text=data.get("text", ""),
            page_number=data.get("page_number", 0),
            color=data.get("color", "#ffeb3b"),
            position=data.get("position", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            tags=data.get("tags", []),
            resolved=data.get("resolved", False),
        )


@dataclass
class LibraryEntry:
    """A single entry in the personal research library."""
    entry_id: str
    title: str
    authors: list[Author] = field(default_factory=list)
    abstract: str = ""
    year: str = ""
    venue: str = ""
    url: str = ""
    doi: str = ""
    arxiv_id: str = ""
    pdf_path: str = ""
    bibtex: str = ""
    tags: list[str] = field(default_factory=list)
    tag_suggestions: list[TagSuggestion] = field(default_factory=list)
    collections: list[str] = field(default_factory=list)
    status: LibraryEntryStatus = LibraryEntryStatus.IMPORTED
    reading_status: ReadingListStatus = ReadingListStatus.TO_READ
    reading_priority: int = 0  # 0 = unset, 1-5 priority
    notes: str = ""
    annotations: list[Annotation] = field(default_factory=list)
    source: str = "manual"  # "manual", "zotero", "arxiv", "semantic_scholar", "upload"
    imported_at: str = ""
    last_read_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "title": self.title,
            "authors": [a.to_dict() for a in self.authors],
            "abstract": self.abstract,
            "year": self.year,
            "venue": self.venue,
            "url": self.url,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "pdf_path": self.pdf_path,
            "bibtex": self.bibtex,
            "tags": self.tags,
            "tag_suggestions": [ts.to_dict() for ts in self.tag_suggestions],
            "collections": self.collections,
            "status": self.status.value,
            "reading_status": self.reading_status.value,
            "reading_priority": self.reading_priority,
            "notes": self.notes,
            "annotations": [a.to_dict() for a in self.annotations],
            "source": self.source,
            "imported_at": self.imported_at,
            "last_read_at": self.last_read_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LibraryEntry:
        return cls(
            entry_id=data["entry_id"],
            title=data.get("title", ""),
            authors=[Author.from_dict(a) for a in data.get("authors", [])],
            abstract=data.get("abstract", ""),
            year=data.get("year", ""),
            venue=data.get("venue", ""),
            url=data.get("url", ""),
            doi=data.get("doi", ""),
            arxiv_id=data.get("arxiv_id", ""),
            pdf_path=data.get("pdf_path", ""),
            bibtex=data.get("bibtex", ""),
            tags=data.get("tags", []),
            tag_suggestions=[TagSuggestion.from_dict(ts) for ts in data.get("tag_suggestions", [])],
            collections=data.get("collections", []),
            status=LibraryEntryStatus(data.get("status", "imported")),
            reading_status=ReadingListStatus(data.get("reading_status", "to_read")),
            reading_priority=data.get("reading_priority", 0),
            notes=data.get("notes", ""),
            annotations=[Annotation.from_dict(a) for a in data.get("annotations", [])],
            source=data.get("source", "manual"),
            imported_at=data.get("imported_at", ""),
            last_read_at=data.get("last_read_at", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class SmartCollection:
    """A smart collection defined by rules for automatic paper classification."""
    collection_id: str
    name: str
    description: str = ""
    icon: str = "📁"
    rules: dict[str, Any] = field(default_factory=dict)
    # rule examples:
    # {"field": "tags", "operator": "contains", "value": "transformer"}
    # {"field": "year", "operator": ">=", "value": "2024"}
    # {"field": "venue", "operator": "in", "value": ["NeurIPS", "ICML", "ICLR"]}
    member_ids: list[str] = field(default_factory=list)
    is_dynamic: bool = True  # Dynamic = auto-populated based on rules
    color: str = "#8b5cf6"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_id": self.collection_id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "rules": self.rules,
            "member_ids": self.member_ids,
            "is_dynamic": self.is_dynamic,
            "color": self.color,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SmartCollection:
        return cls(
            collection_id=data["collection_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            icon=data.get("icon", "📁"),
            rules=data.get("rules", {}),
            member_ids=data.get("member_ids", []),
            is_dynamic=data.get("is_dynamic", True),
            color=data.get("color", "#8b5cf6"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class ZoteroImportResult:
    """Result of a Zotero import operation."""
    success: bool
    entries_imported: int = 0
    entries_skipped: int = 0
    entries: list[LibraryEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "entries_imported": self.entries_imported,
            "entries_skipped": self.entries_skipped,
            "entries": [e.to_dict() for e in self.entries],
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class LibraryStats:
    """Aggregate statistics about the personal library."""
    total_entries: int = 0
    total_read: int = 0
    total_unread: int = 0
    total_annotations: int = 0
    total_collections: int = 0
    tag_counts: dict[str, int] = field(default_factory=dict)
    venue_counts: dict[str, int] = field(default_factory=dict)
    year_counts: dict[str, int] = field(default_factory=dict)
    recent_entries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_entries": self.total_entries,
            "total_read": self.total_read,
            "total_unread": self.total_unread,
            "total_annotations": self.total_annotations,
            "total_collections": self.total_collections,
            "tag_counts": self.tag_counts,
            "venue_counts": self.venue_counts,
            "year_counts": self.year_counts,
            "recent_entries": self.recent_entries,
        }


# ── Pydantic models (API serialisation for routes and collections) ─────────


class MatchOperator(str, Enum):
    """Operators for smart collection rule matching."""
    EQUALS = "equals"
    CONTAINS = "contains"
    STARTSWITH = "startswith"
    REGEX = "regex"
    TAG_CONTAINS = "tag_contains"
    YEAR_RANGE = "year_range"


class CollectionRule(BaseModel):
    """A single matching rule for a smart collection."""
    field: str
    operator: MatchOperator
    value: str


class LibraryItem(BaseModel):
    """Pydantic model for API serialisation of a library item."""
    id: str = ""
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    published_at: str = ""
    year: str = ""
    venue: str = ""
    url: str = ""
    doi: str = ""
    arxiv_id: str = ""
    pdf_path: str = ""
    bibtex: str = ""
    tags: list[str] = Field(default_factory=list)
    collections: list[str] = Field(default_factory=list)
    kind: str = "article"  # article, book, thesis, report, conference, etc.
    source: str = "manual"  # manual, zotero, bibtex, arxiv
    notes: str = ""
    imported_at: str = ""
    created_at: str = ""
    updated_at: str = ""


class Collection(BaseModel):
    """Pydantic model for API serialisation of a collection."""
    id: str
    name: str
    description: str = ""
    icon: str = "📁"
    color: str = "#8b5cf6"
    rules: list[CollectionRule] = Field(default_factory=list)
    item_ids: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    is_dynamic: bool = False
    created_at: str = ""
    updated_at: str = ""
