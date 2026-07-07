"""Reading list manager — track what to read, in progress, or completed."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import uuid4
from typing import Any

from pydantic import BaseModel, Field


class ReadingStatus(str, Enum):
    TO_READ = "to_read"
    READING = "reading"
    COMPLETED = "completed"
    REFERENCE = "reference"  # used as citation, not read cover-to-cover


class ReadingPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReadingListItem(BaseModel):
    """An entry in a user's reading list."""

    id: str
    item_id: str  # FK → LibraryItem.id
    status: ReadingStatus = ReadingStatus.TO_READ
    priority: ReadingPriority = ReadingPriority.MEDIUM
    added_at: str = ""
    updated_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    rating: int | None = None  # 1-5 star rating
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    progress_pct: int = 0  # 0-100
    current_page: int = 0
    total_pages: int | None = None
    goal_date: str | None = None  # ISO date when user plans to finish


# ── Storage ────────────────────────────────────────────────────────────────


def _reading_list_path() -> Path:
    p = Path(".runtime/personal_library/reading_list.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_all() -> list[dict[str, Any]]:
    p = _reading_list_path()
    if not p.exists():
        return []
    raw = p.read_text(encoding="utf-8")
    return json.loads(raw) if raw.strip() else []


def _save_all(items: list[dict[str, Any]]) -> None:
    p = _reading_list_path()
    p.write_text(json.dumps(items, indent=2, default=str), encoding="utf-8")


# ── CRUD ───────────────────────────────────────────────────────────────────


def list_reading_list(
    status: ReadingStatus | None = None,
) -> list[ReadingListItem]:
    all_items = _load_all()
    if status:
        all_items = [i for i in all_items if i.get("status") == status.value]
    return [ReadingListItem(**i) for i in all_items]


def get_reading_entry(item_id: str) -> ReadingListItem | None:
    for i in _load_all():
        if i["item_id"] == item_id:
            return ReadingListItem(**i)
    return None


def add_to_reading_list(
    item_id: str,
    priority: ReadingPriority = ReadingPriority.MEDIUM,
    notes: str = "",
    tags: list[str] | None = None,
    goal_date: str | None = None,
    total_pages: int | None = None,
) -> ReadingListItem:
    items = _load_all()
    now = datetime.utcnow().isoformat() + "Z"

    # Don't duplicate
    for i in items:
        if i["item_id"] == item_id:
            raise ValueError(f"Item {item_id} is already in the reading list")

    entry = ReadingListItem(
        id=_next_id(),
        item_id=item_id,
        status=ReadingStatus.TO_READ,
        priority=priority,
        added_at=now,
        updated_at=now,
        notes=notes,
        tags=tags or [],
        total_pages=total_pages,
        goal_date=goal_date,
    )
    items.append(entry.model_dump())
    _save_all(items)
    return entry


def update_reading_entry(
    item_id: str,
    updates: dict[str, Any],
) -> ReadingListItem | None:
    items = _load_all()
    now = datetime.utcnow().isoformat() + "Z"

    for i in items:
        if i["item_id"] == item_id:
            # If status changed, auto-set timestamps
            if updates.get("status") == ReadingStatus.READING.value and not i.get("started_at"):
                updates["started_at"] = now
            if updates.get("status") == ReadingStatus.COMPLETED.value and not i.get("completed_at"):
                updates["completed_at"] = now
                updates["progress_pct"] = 100

            i.update(updates)
            i["updated_at"] = now
            _save_all(items)
            return ReadingListItem(**i)
    return None


def remove_from_reading_list(item_id: str) -> bool:
    items = _load_all()
    before = len(items)
    items = [i for i in items if i["item_id"] != item_id]
    if len(items) == before:
        return False
    _save_all(items)
    return True


# ── stats ───────────────────────────────────────────────────────────────────


def reading_list_stats() -> dict[str, Any]:
    items = _load_all()
    counts: dict[str, int] = {}
    for i in items:
        s = i.get("status", "to_read")
        counts[s] = counts.get(s, 0) + 1
    return {
        "total": len(items),
        "by_status": counts,
        "completed": counts.get("completed", 0),
        "reading": counts.get("reading", 0),
        "to_read": counts.get("to_read", 0),
    }


# ── helpers ─────────────────────────────────────────────────────────────────


_counter: int = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"rl-{uuid4().hex[:8]}"
