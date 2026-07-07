"""
P28: Personal Research Library — Core Storage

Provides in-memory + JSON file persistent storage for library entries,
smart collections, annotations, and reading list state.

Exposes both a class (PersonalLibrary) and standalone functions that
operate on a module-level singleton for route convenience.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from research_agent.personal_library.models import (
    LibraryEntry,
    LibraryEntryStatus,
    SmartCollection,
    ReadingListStatus,
    Annotation,
    AnnotationType,
    LibraryStats,
    Author,
    LibraryItem,
)

logger = logging.getLogger(__name__)


class PersonalLibrary:
    """Core personal research library with JSON file persistence.

    Manages:
    - Library entries (papers, PDFs, etc.)
    - Tags and auto-tag suggestions
    - Collections (static and dynamic/smart)
    - Annotations (highlights, notes)
    - Reading list status tracking
    """

    def __init__(self, store_path: str | Path = ".runtime/personal_library.json"):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, LibraryEntry] = {}
        self._collections: dict[str, SmartCollection] = {}
        self._dirty: bool = False
        self._load()

    # ── Persistence ──────────────────────────────────────────

    def _load(self) -> None:
        """Load library state from disk."""
        if not self.store_path.exists():
            logger.info("No existing library state found at %s", self.store_path)
            return
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
            self._entries = {
                eid: LibraryEntry.from_dict(ed)
                for eid, ed in data.get("entries", {}).items()
            }
            self._collections = {
                cid: SmartCollection.from_dict(cd)
                for cid, cd in data.get("collections", {}).items()
            }
            logger.info(
                "Loaded library: %d entries, %d collections",
                len(self._entries),
                len(self._collections),
            )
        except Exception as exc:
            logger.warning("Failed to load library: %s", exc)
            self._entries = {}
            self._collections = {}

    def _save(self) -> None:
        """Save library state to disk."""
        try:
            data = {
                "entries": {eid: entry.to_dict() for eid, entry in self._entries.items()},
                "collections": {cid: col.to_dict() for cid, col in self._collections.items()},
            }
            self.store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self._dirty = False
        except Exception as exc:
            logger.error("Failed to save library: %s", exc)

    def _ensure_saved(self) -> None:
        if self._dirty:
            self._save()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _make_id(self) -> str:
        return f"lib-{uuid.uuid4().hex[:12]}"

    # ── Entry CRUD ───────────────────────────────────────────

    def add_entry(self, entry: LibraryEntry) -> LibraryEntry:
        """Add a new entry to the library."""
        if not entry.entry_id:
            entry.entry_id = self._make_id()
        entry.created_at = self._now()
        entry.updated_at = self._now()
        entry.imported_at = self._now()
        self._entries[entry.entry_id] = entry
        self._dirty = True
        self._ensure_saved()
        return entry

    def get_entry(self, entry_id: str) -> LibraryEntry | None:
        return self._entries.get(entry_id)

    def update_entry(self, entry_id: str, updates: dict[str, Any]) -> LibraryEntry | None:
        entry = self._entries.get(entry_id)
        if not entry:
            return None
        for key, value in updates.items():
            if hasattr(entry, key) and key not in ("entry_id", "created_at", "imported_at"):
                if key == "tags" and isinstance(value, list):
                    entry.tags = list(set(entry.tags + value)) if entry.tags else value
                elif key == "collections" and isinstance(value, list):
                    entry.collections = list(set(entry.collections + value))
                elif key == "reading_status":
                    entry.reading_status = ReadingListStatus(value)
                    if value == ReadingListStatus.COMPLETED.value or value == ReadingListStatus.COMPLETED:
                        entry.last_read_at = self._now()
                elif key == "status":
                    entry.status = LibraryEntryStatus(value)
                else:
                    setattr(entry, key, value)
        entry.updated_at = self._now()
        self._dirty = True
        self._ensure_saved()
        return entry

    def delete_entry(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            # Remove from collections
            for col in self._collections.values():
                if entry_id in col.member_ids:
                    col.member_ids.remove(entry_id)
            self._dirty = True
            self._ensure_saved()
            return True
        return False

    def list_entries(
        self,
        collection_id: str | None = None,
        tag: str | None = None,
        status: str | None = None,
        reading_status: str | None = None,
        search: str | None = None,
        sort_by: str = "updated_at",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[LibraryEntry], int]:
        """List entries with optional filtering and pagination."""
        entries = list(self._entries.values())

        # Filter by collection
        if collection_id:
            col = self._collections.get(collection_id)
            if col:
                entries = [e for e in entries if e.entry_id in col.member_ids]
            else:
                entries = [e for e in entries if collection_id in e.collections]

        # Filter by tag
        if tag:
            entries = [e for e in entries if tag in e.tags]

        # Filter by status
        if status:
            try:
                st = LibraryEntryStatus(status)
                entries = [e for e in entries if e.status == st]
            except ValueError:
                pass

        # Filter by reading status
        if reading_status:
            try:
                rs = ReadingListStatus(reading_status)
                entries = [e for e in entries if e.reading_status == rs]
            except ValueError:
                pass

        # Text search across title, abstract, authors, tags
        if search:
            q = search.lower()
            entries = [
                e for e in entries
                if q in e.title.lower()
                or q in e.abstract.lower()
                or any(q in a.name.lower() for a in e.authors)
                or any(q in t.lower() for t in e.tags)
            ]

        total = len(entries)

        # Sort
        reverse = sort_by.startswith("-")
        sort_key = sort_by.lstrip("-")
        if sort_key == "title":
            entries.sort(key=lambda e: e.title.lower(), reverse=reverse)
        elif sort_key == "year":
            entries.sort(key=lambda e: e.year, reverse=not reverse)
        elif sort_key == "reading_priority":
            entries.sort(key=lambda e: e.reading_priority, reverse=not reverse)
        elif sort_key == "created_at":
            entries.sort(key=lambda e: e.created_at, reverse=not reverse)
        else:  # updated_at
            entries.sort(key=lambda e: e.updated_at, reverse=not reverse)

        # Paginate
        paginated = entries[offset:offset + limit]

        return paginated, total

    # ── Annotation Management ────────────────────────────────

    def add_annotation(self, entry_id: str, annotation: Annotation) -> Annotation | None:
        entry = self._entries.get(entry_id)
        if not entry:
            return None
        if not annotation.annotation_id:
            annotation.annotation_id = f"ann-{uuid.uuid4().hex[:10]}"
        annotation.entry_id = entry_id
        annotation.created_at = self._now()
        annotation.updated_at = self._now()
        entry.annotations.append(annotation)
        self._dirty = True
        self._ensure_saved()
        return annotation

    def get_annotations(self, entry_id: str) -> list[Annotation]:
        entry = self._entries.get(entry_id)
        return list(entry.annotations) if entry else []

    def update_annotation(self, entry_id: str, annotation_id: str, updates: dict[str, Any]) -> Annotation | None:
        entry = self._entries.get(entry_id)
        if not entry:
            return None
        for ann in entry.annotations:
            if ann.annotation_id == annotation_id:
                for key, value in updates.items():
                    if hasattr(ann, key) and key not in ("annotation_id", "entry_id", "created_at"):
                        if key == "annotation_type":
                            ann.annotation_type = AnnotationType(value)
                        else:
                            setattr(ann, key, value)
                ann.updated_at = self._now()
                self._dirty = True
                self._ensure_saved()
                return ann
        return None

    def delete_annotation(self, entry_id: str, annotation_id: str) -> bool:
        entry = self._entries.get(entry_id)
        if not entry:
            return False
        for i, ann in enumerate(entry.annotations):
            if ann.annotation_id == annotation_id:
                entry.annotations.pop(i)
                self._dirty = True
                self._ensure_saved()
                return True
        return False

    # ── Tag Management ───────────────────────────────────────

    def get_all_tags(self) -> list[dict[str, Any]]:
        """Get all unique tags with usage counts."""
        tag_counts: dict[str, int] = {}
        for entry in self._entries.values():
            for tag in entry.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            for ts in entry.tag_suggestions:
                tag_counts[ts.tag] = tag_counts.get(ts.tag, 0) + 1
        return [
            {"tag": tag, "count": count}
            for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])
        ]

    # ── Collection Management ────────────────────────────────

    def add_collection(self, collection: SmartCollection) -> SmartCollection:
        if not collection.collection_id:
            collection.collection_id = f"col-{uuid.uuid4().hex[:10]}"
        collection.created_at = self._now()
        collection.updated_at = self._now()
        self._collections[collection.collection_id] = collection
        self._dirty = True
        self._ensure_saved()
        return collection

    def get_collection(self, collection_id: str) -> SmartCollection | None:
        return self._collections.get(collection_id)

    def update_collection(self, collection_id: str, updates: dict[str, Any]) -> SmartCollection | None:
        col = self._collections.get(collection_id)
        if not col:
            return None
        for key, value in updates.items():
            if hasattr(col, key) and key not in ("collection_id", "created_at"):
                setattr(col, key, value)
        col.updated_at = self._now()
        self._dirty = True
        self._ensure_saved()
        return col

    def delete_collection(self, collection_id: str) -> bool:
        if collection_id in self._collections:
            del self._collections[collection_id]
            self._dirty = True
            self._ensure_saved()
            return True
        return False

    def list_collections(self) -> list[SmartCollection]:
        return list(self._collections.values())

    def add_entry_to_collection(self, entry_id: str, collection_id: str) -> bool:
        col = self._collections.get(collection_id)
        if not col:
            return False
        entry = self._entries.get(entry_id)
        if not entry:
            return False
        if entry_id not in col.member_ids:
            col.member_ids.append(entry_id)
        if collection_id not in entry.collections:
            entry.collections.append(collection_id)
        col.updated_at = self._now()
        entry.updated_at = self._now()
        self._dirty = True
        self._ensure_saved()
        return True

    def remove_entry_from_collection(self, entry_id: str, collection_id: str) -> bool:
        col = self._collections.get(collection_id)
        entry = self._entries.get(entry_id)
        if col and entry_id in col.member_ids:
            col.member_ids.remove(entry_id)
            col.updated_at = self._now()
        if entry and collection_id in entry.collections:
            entry.collections.remove(collection_id)
            entry.updated_at = self._now()
        self._dirty = True
        self._ensure_saved()
        return True

    # ── Statistics ───────────────────────────────────────────

    def get_stats(self) -> LibraryStats:
        stats = LibraryStats()
        stats.total_entries = len(self._entries)
        stats.total_collections = len(self._collections)

        tag_counts: dict[str, int] = {}
        venue_counts: dict[str, int] = {}
        year_counts: dict[str, int] = {}
        total_annotations = 0
        total_read = 0
        total_unread = 0

        for entry in self._entries.values():
            for tag in entry.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            if entry.venue:
                venue_counts[entry.venue] = venue_counts.get(entry.venue, 0) + 1
            if entry.year:
                year_counts[entry.year] = year_counts.get(entry.year, 0) + 1
            total_annotations += len(entry.annotations)
            if entry.reading_status == ReadingListStatus.COMPLETED:
                total_read += 1
            elif entry.reading_status == ReadingListStatus.TO_READ:
                total_unread += 1

        stats.tag_counts = dict(sorted(tag_counts.items(), key=lambda x: -x[1])[:30])
        stats.venue_counts = dict(sorted(venue_counts.items(), key=lambda x: -x[1])[:15])
        stats.year_counts = dict(sorted(year_counts.items()))
        stats.total_annotations = total_annotations
        stats.total_read = total_read
        stats.total_unread = total_unread

        # Recent entries
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda e: e.updated_at,
            reverse=True,
        )[:10]
        stats.recent_entries = [
            {
                "entry_id": e.entry_id,
                "title": e.title,
                "authors": [a.name for a in e.authors[:3]],
                "year": e.year,
                "tags": e.tags[:5],
                "reading_status": e.reading_status.value,
                "updated_at": e.updated_at,
            }
            for e in sorted_entries
        ]

        return stats

    # ── Bulk Operations ──────────────────────────────────────

    def import_entries(self, entries: list[LibraryEntry]) -> list[LibraryEntry]:
        """Import multiple entries at once (from Zotero, BibTeX, etc.)."""
        imported: list[LibraryEntry] = []
        for entry in entries:
            # Deduplicate by DOI or title
            is_duplicate = False
            for existing in self._entries.values():
                if entry.doi and existing.doi == entry.doi:
                    is_duplicate = True
                    break
                if entry.title.lower() == existing.title.lower():
                    is_duplicate = True
                    break

            if not is_duplicate:
                self.add_entry(entry)
                imported.append(entry)

        self._dirty = True
        self._ensure_saved()
        return imported


# ── Standalone functions (used by routes.py for convenience) ────────────────

_library_instance: PersonalLibrary | None = None


def _get_library() -> PersonalLibrary:
    global _library_instance
    if _library_instance is None:
        _library_instance = PersonalLibrary()
    return _library_instance


def _entry_to_item(entry: LibraryEntry) -> LibraryItem:
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


def _item_to_entry(item: LibraryItem) -> LibraryEntry:
    """Convert a LibraryItem Pydantic model to a LibraryEntry dataclass."""
    return LibraryEntry(
        entry_id=item.id,
        title=item.title,
        authors=[Author(name=a) for a in item.authors],
        abstract=item.abstract,
        year=item.year or item.published_at,
        venue=item.venue,
        url=item.url,
        doi=item.doi,
        arxiv_id=item.arxiv_id,
        pdf_path=item.pdf_path,
        bibtex=item.bibtex,
        tags=item.tags,
        collections=item.collections,
        source=item.source,
        notes=item.notes,
        status=LibraryEntryStatus.IMPORTED,
        reading_status=ReadingListStatus.TO_READ,
    )


def add_item(item: LibraryItem) -> LibraryItem:
    entry = _item_to_entry(item)
    saved = _get_library().add_entry(entry)
    return _entry_to_item(saved)


def get_item(item_id: str) -> LibraryItem | None:
    entry = _get_library().get_entry(item_id)
    return _entry_to_item(entry) if entry else None


def update_item(item_id: str, updates: dict[str, Any]) -> LibraryItem | None:
    entry = _get_library().update_entry(item_id, updates)
    return _entry_to_item(entry) if entry else None


def delete_item(item_id: str) -> bool:
    return _get_library().delete_entry(item_id)


def list_items(limit: int = 50, offset: int = 0) -> list[LibraryItem]:
    entries, _ = _get_library().list_entries(limit=limit, offset=offset)
    return [_entry_to_item(e) for e in entries]


def search_items(query: str, limit: int = 50) -> list[LibraryItem]:
    entries, _ = _get_library().list_entries(search=query, limit=limit)
    return [_entry_to_item(e) for e in entries]


def import_items(items: list[LibraryItem]) -> list[LibraryItem]:
    entries = [_item_to_entry(it) for it in items]
    saved = _get_library().import_entries(entries)
    return [_entry_to_item(e) for e in saved]
