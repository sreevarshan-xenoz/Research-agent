"""P28 — Personal Research Library API routes.

Endpoints cover library items, Zotero/BibTeX import, LLM auto-tagging,
smart collections, PDF annotations, and reading-list management.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from research_agent.app.auth import current_active_user, User
from research_agent.personal_library.annotation import (
    Annotation,
    AnnotationRegion,
    create_annotation,
    delete_annotation,
    delete_annotations_for_item,
    list_annotations,
    update_annotation,
)
from research_agent.personal_library.collections import (
    Collection,
    CollectionRule,
    add_item_to_collection,
    create_collection,
    delete_collection,
    get_collection,
    list_collections,
    remove_item_from_collection,
    update_collection,
)
from research_agent.personal_library.library import (
    LibraryItem,
    add_item,
    delete_item,
    get_item,
    list_items,
    search_items,
    update_item,
    import_items,
)
from research_agent.personal_library.reading_list import (
    ReadingListItem,
    ReadingPriority,
    ReadingStatus,
    add_to_reading_list,
    list_reading_list,
    reading_list_stats,
    remove_from_reading_list,
    update_reading_entry,
)
from research_agent.personal_library.tagger import auto_tag_item, get_suggested_tags
from research_agent.personal_library.zotero import (
    import_from_bibtex,
    import_from_zotero_json,
)

router = APIRouter(prefix="/api/personal-library", tags=["Personal Library"])


# ── Library items ──────────────────────────────────────────────────────────


@router.get("/items")
async def list_library_items(
    q: str = "",
    tags: str = "",
    collections: str = "",
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(current_active_user),
) -> list[LibraryItem]:
    """List library items with optional search/filter."""
    if q:
        return search_items(q, limit=limit)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    col_list = [c.strip() for c in collections.split(",") if c.strip()] if collections else []
    items = list_items(limit=limit, offset=offset)
    if tag_list:
        items = [it for it in items if any(t in (it.tags or []) for t in tag_list)]
    if col_list:
        items = [it for it in items if col_list and it.collections and any(c in (it.collections or []) for c in col_list)]
    return items


@router.get("/items/{item_id}")
async def get_library_item(
    item_id: str,
    user: User = Depends(current_active_user),
) -> LibraryItem:
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    return item


@router.post("/items")
async def create_library_item(
    item: LibraryItem,
    user: User = Depends(current_active_user),
) -> LibraryItem:
    existing = get_item(item.id)
    if existing:
        raise HTTPException(status_code=409, detail="Item with this ID already exists")
    return add_item(item)


@router.put("/items/{item_id}")
async def update_library_item(
    item_id: str,
    updates: dict[str, Any],
    user: User = Depends(current_active_user),
) -> LibraryItem:
    updated = update_item(item_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Library item not found")
    return updated


@router.delete("/items/{item_id}")
async def delete_library_item(
    item_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, bool]:
    deleted = delete_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Library item not found")
    # Clean up any orphaned annotations
    delete_annotations_for_item(item_id)
    return {"deleted": True}


# ── Import ─────────────────────────────────────────────────────────────────


@router.post("/import/bibtex")
async def import_bibtex(
    content: str,
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Import references from BibTeX string."""
    try:
        items = import_from_bibtex(content)
        saved = import_items(items)
        return {"imported": len(saved), "items": saved}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"BibTeX import failed: {e}")


@router.post("/import/zotero")
async def import_zotero(
    content: str,
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Import references from Zotero JSON export."""
    try:
        items = import_from_zotero_json(content)
        saved = import_items(items)
        return {"imported": len(saved), "items": saved}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Zotero import failed: {e}")


@router.post("/import/file")
async def import_library_file(
    file: UploadFile = File(...),
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Import a BibTeX or Zotero JSON file."""
    raw = await file.read()
    content = raw.decode("utf-8", errors="replace")
    fname = (file.filename or "").lower()

    if fname.endswith(".bib") or fname.endswith(".bibtex"):
        return await import_bibtex(content, user=user)

    try:
        json.loads(content)  # validate JSON
        return await import_zotero(content, user=user)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Unrecognised file format. Use .bib or Zotero JSON export.")


# ── Auto-tagging ───────────────────────────────────────────────────────────


@router.post("/items/{item_id}/auto-tag")
async def tag_item(
    item_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, list[str]]:
    """Run LLM-based auto-tagging on a library item."""
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    tags = await auto_tag_item(item)
    if tags:
        existing = set(item.tags or [])
        merged = list(existing | set(tags))
        update_item(item_id, {"tags": merged})
    return {"tags": tags}


@router.get("/items/{item_id}/suggested-tags")
async def suggested_tags(
    item_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, list[str]]:
    """Get tag suggestions without saving them."""
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    tags = get_suggested_tags(item)
    return {"tags": tags}


# ── Smart Collections ──────────────────────────────────────────────────────


@router.get("/collections")
async def list_user_collections(
    user: User = Depends(current_active_user),
) -> list[Collection]:
    return list_collections()


@router.get("/collections/{collection_id}")
async def get_user_collection(
    collection_id: str,
    user: User = Depends(current_active_user),
) -> Collection:
    col = get_collection(collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    return col


@router.post("/collections")
async def create_user_collection(
    name: str,
    description: str = "",
    rules: list[CollectionRule] | None = None,
    parent_id: str | None = None,
    icon: str = "📁",
    user: User = Depends(current_active_user),
) -> Collection:
    return create_collection(
        name=name,
        description=description,
        rules=rules,
        parent_id=parent_id,
        icon=icon,
    )


@router.put("/collections/{collection_id}")
async def update_user_collection(
    collection_id: str,
    updates: dict[str, Any],
    user: User = Depends(current_active_user),
) -> Collection:
    col = update_collection(collection_id, updates)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    return col


@router.delete("/collections/{collection_id}")
async def delete_user_collection(
    collection_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, bool]:
    if not delete_collection(collection_id):
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"deleted": True}


@router.post("/collections/{collection_id}/items/{item_id}")
async def add_item_to_user_collection(
    collection_id: str,
    item_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, bool]:
    if not add_item_to_collection(collection_id, item_id):
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"success": True}


@router.delete("/collections/{collection_id}/items/{item_id}")
async def remove_item_from_user_collection(
    collection_id: str,
    item_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, bool]:
    if not remove_item_from_collection(collection_id, item_id):
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"success": True}


# ── Annotations ────────────────────────────────────────────────────────────


@router.get("/items/{item_id}/annotations")
async def get_item_annotations(
    item_id: str,
    user: User = Depends(current_active_user),
) -> list[Annotation]:
    return list_annotations(item_id=item_id)


@router.post("/items/{item_id}/annotations")
async def create_item_annotation(
    item_id: str,
    kind: str = "highlight",
    region: AnnotationRegion | None = None,
    color: str = "#ffff00",
    text: str = "",
    note: str = "",
    tags: list[str] | None = None,
    user: User = Depends(current_active_user),
) -> Annotation:
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    return create_annotation(
        item_id=item_id,
        kind=kind,
        region=region,
        color=color,
        text=text,
        note=note,
        tags=tags,
    )


@router.put("/annotations/{annotation_id}")
async def update_item_annotation(
    annotation_id: str,
    updates: dict[str, Any],
    user: User = Depends(current_active_user),
) -> Annotation:
    ann = update_annotation(annotation_id, updates)
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return ann


@router.delete("/annotations/{annotation_id}")
async def delete_item_annotation(
    annotation_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, bool]:
    if not delete_annotation(annotation_id):
        raise HTTPException(status_code=404, detail="Annotation not found")
    return {"deleted": True}


# ── Reading List ───────────────────────────────────────────────────────────


@router.get("/reading-list")
async def get_reading_list(
    status: str | None = None,
    user: User = Depends(current_active_user),
) -> list[ReadingListItem]:
    s = ReadingStatus(status) if status else None
    return list_reading_list(status=s)


@router.get("/reading-list/stats")
async def get_reading_list_stats(
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    return reading_list_stats()


@router.post("/reading-list/{item_id}")
async def add_to_reading_list_endpoint(
    item_id: str,
    priority: str = "medium",
    notes: str = "",
    tags: list[str] | None = None,
    goal_date: str | None = None,
    total_pages: int | None = None,
    user: User = Depends(current_active_user),
) -> ReadingListItem:
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    try:
        p = ReadingPriority(priority)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")
    return add_to_reading_list(
        item_id=item_id,
        priority=p,
        notes=notes,
        tags=tags,
        goal_date=goal_date,
        total_pages=total_pages,
    )


@router.put("/reading-list/{item_id}")
async def update_reading_list_entry(
    item_id: str,
    updates: dict[str, Any],
    user: User = Depends(current_active_user),
) -> ReadingListItem:
    entry = update_reading_entry(item_id, updates)
    if not entry:
        raise HTTPException(status_code=404, detail="Reading list entry not found")
    return entry


@router.delete("/reading-list/{item_id}")
async def remove_from_reading_list_endpoint(
    item_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, bool]:
    if not remove_from_reading_list(item_id):
        raise HTTPException(status_code=404, detail="Reading list entry not found")
    return {"deleted": True}


# ── Library stats ──────────────────────────────────────────────────────────


@router.get("/stats/summary")
async def personal_library_stats(
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    items = list_items()
    total = len(items)
    tags_counter: dict[str, int] = {}
    authors_counter: dict[str, int] = {}
    years_counter: dict[str, int] = {}
    types_counter: dict[str, int] = {}
    collections_list = list_collections()

    for it in items:
        for t in (it.tags or []):
            tags_counter[t] = tags_counter.get(t, 0) + 1
        for a in (it.authors or []):
            authors_counter[a] = authors_counter.get(a, 0) + 1
        if it.published_at and len(it.published_at) >= 4:
            y = it.published_at[:4]
            years_counter[y] = years_counter.get(y, 0) + 1
        t = it.kind or "unknown"
        types_counter[t] = types_counter.get(t, 0) + 1

    from collections import Counter

    return {
        "total_items": total,
        "total_collections": len(collections_list),
        "top_tags": dict(Counter(tags_counter).most_common(20)),
        "top_authors": dict(Counter(authors_counter).most_common(20)),
        "years": dict(sorted(years_counter.items())),
        "types": types_counter,
    }
