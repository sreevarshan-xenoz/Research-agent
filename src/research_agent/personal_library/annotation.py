"""PDF annotation store — highlights, sticky notes, and region markers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from uuid import uuid4

from pydantic import BaseModel, Field


class AnnotationRegion(BaseModel):
    """A rectangular region on a PDF page (normalised 0-1 coordinates)."""

    page: int
    x: float
    y: float
    width: float
    height: float


class Annotation(BaseModel):
    """A single annotation — highlight, underline, sticky note, or free-text."""

    id: str
    item_id: str
    kind: str = "highlight"  # highlight | underline | note | free_text
    region: AnnotationRegion | None = None
    color: str = "#ffff00"  # hex colour
    text: str = ""  # highlighted / selected text
    note: str = ""  # user's typed note
    created_at: str = ""
    updated_at: str = ""
    tags: list[str] = Field(default_factory=list)


# ── Storage ────────────────────────────────────────────────────────────────


def _annotations_path() -> Path:
    p = Path(".runtime/personal_library/annotations.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_all_annotations() -> list[dict[str, Any]]:
    p = _annotations_path()
    if not p.exists():
        return []
    raw = p.read_text(encoding="utf-8")
    return json.loads(raw) if raw.strip() else []


def _save_all_annotations(annotations: list[dict[str, Any]]) -> None:
    p = _annotations_path()
    p.write_text(json.dumps(annotations, indent=2, default=str), encoding="utf-8")


# ── CRUD ───────────────────────────────────────────────────────────────────


def list_annotations(item_id: str | None = None) -> list[Annotation]:
    all_a = _load_all_annotations()
    if item_id:
        all_a = [a for a in all_a if a.get("item_id") == item_id]
    return [Annotation(**a) for a in all_a]


def get_annotation(annotation_id: str) -> Annotation | None:
    for a in _load_all_annotations():
        if a["id"] == annotation_id:
            return Annotation(**a)
    return None


def create_annotation(
    item_id: str,
    kind: str = "highlight",
    region: AnnotationRegion | None = None,
    color: str = "#ffff00",
    text: str = "",
    note: str = "",
    tags: list[str] | None = None,
) -> Annotation:
    annotations = _load_all_annotations()
    now = datetime.utcnow().isoformat() + "Z"
    ann = Annotation(
        id=_next_ann_id(),
        item_id=item_id,
        kind=kind,
        region=region,
        color=color,
        text=text,
        note=note,
        created_at=now,
        updated_at=now,
        tags=tags or [],
    )
    annotations.append(ann.model_dump())
    _save_all_annotations(annotations)
    return ann


def update_annotation(
    annotation_id: str,
    updates: dict[str, Any],
) -> Annotation | None:
    annotations = _load_all_annotations()
    for a in annotations:
        if a["id"] == annotation_id:
            a.update(updates)
            a["updated_at"] = datetime.utcnow().isoformat() + "Z"
            _save_all_annotations(annotations)
            return Annotation(**a)
    return None


def delete_annotation(annotation_id: str) -> bool:
    annotations = _load_all_annotations()
    before = len(annotations)
    annotations = [a for a in annotations if a["id"] != annotation_id]
    if len(annotations) == before:
        return False
    _save_all_annotations(annotations)
    return True


def delete_annotations_for_item(item_id: str) -> int:
    """Delete all annotations belonging to a library item. Returns count."""
    annotations = _load_all_annotations()
    before = len(annotations)
    annotations = [a for a in annotations if a.get("item_id") != item_id]
    removed = before - len(annotations)
    if removed:
        _save_all_annotations(annotations)
    return removed


# ── helpers ─────────────────────────────────────────────────────────────────


_ann_counter: int = 0


def _next_ann_id() -> str:
    global _ann_counter
    _ann_counter += 1
    return f"ann-{uuid4().hex[:8]}"
