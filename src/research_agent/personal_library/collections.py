"""Smart collections — auto-filter rules + manual groupings for personal library."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from research_agent.personal_library.models import (
    Collection,
    CollectionRule,
    LibraryItem,
    MatchOperator,
)


def _get_collections_path() -> Path:
    path = Path(".runtime/personal_library/collections.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ── Storage ────────────────────────────────────────────────────────────────


def _load_collections() -> list[dict[str, Any]]:
    p = _get_collections_path()
    if not p.exists():
        return []
    raw = p.read_text(encoding="utf-8")
    return json.loads(raw) if raw.strip() else []


def _save_collections(collections: list[dict[str, Any]]) -> None:
    p = _get_collections_path()
    p.write_text(json.dumps(collections, indent=2, default=str), encoding="utf-8")


# ── CRUD ───────────────────────────────────────────────────────────────────


def list_collections() -> list[Collection]:
    return [Collection(**c) for c in _load_collections()]


def get_collection(collection_id: str) -> Collection | None:
    for c in _load_collections():
        if c.get("id") == collection_id:
            return Collection(**c)
    return None


def create_collection(
    name: str,
    description: str = "",
    rules: list[CollectionRule] | None = None,
    parent_id: str | None = None,
    icon: str = "📁",
) -> Collection:
    collections = _load_collections()
    now = datetime.utcnow().isoformat() + "Z"
    col = Collection(
        id=f"col-{uuid4().hex[:8]}",
        name=name,
        description=description,
        rules=rules or [],
        parent_id=parent_id,
        icon=icon,
        item_ids=[],
        created_at=now,
        updated_at=now,
    )
    collections.append(col.model_dump())
    _save_collections(collections)
    return col


def update_collection(
    collection_id: str,
    updates: dict[str, Any],
) -> Collection | None:
    collections = _load_collections()
    for i, c in enumerate(collections):
        if c["id"] == collection_id:
            collections[i].update(updates)
            collections[i]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            _save_collections(collections)
            return Collection(**collections[i])
    return None


def delete_collection(collection_id: str) -> bool:
    collections = _load_collections()
    before = len(collections)
    collections = [c for c in collections if c["id"] != collection_id]
    if len(collections) == before:
        return False
    _save_collections(collections)
    return True


# ── Rule evaluation ────────────────────────────────────────────────────────


def _evaluate_rule(item: LibraryItem, rule: CollectionRule) -> bool:
    """Evaluate a single matching rule against a library item."""
    field_value: Any | None = getattr(item, rule.field, None)

    if field_value is None:
        return False

    match rule.operator:
        case MatchOperator.EQUALS:
            return str(field_value).lower() == rule.value.lower()
        case MatchOperator.CONTAINS:
            return rule.value.lower() in str(field_value).lower()
        case MatchOperator.STARTSWITH:
            return str(field_value).lower().startswith(rule.value.lower())
        case MatchOperator.REGEX:
            import re
            return bool(re.search(rule.value, str(field_value), re.IGNORECASE))
        case MatchOperator.TAG_CONTAINS:
            tags = getattr(item, "tags", [])
            return rule.value.lower() in [t.lower() for t in tags]
        case MatchOperator.YEAR_RANGE:
            try:
                year = int(rule.value.split("-")[0])
                end = int(rule.value.split("-")[1]) if "-" in rule.value else year
                pub = item.published_at or ""
                pub_year = int(pub[:4]) if len(pub) >= 4 else 0
                return year <= pub_year <= end
            except (ValueError, IndexError):
                return False
        case _:
            return False


def evaluate_collection_rules(collection: Collection, item: LibraryItem) -> bool:
    """Check if an item matches the rules of a smart collection.

    Rules are AND-ed together — all must match.
    """
    if not collection.rules:
        return False
    return all(_evaluate_rule(item, r) for r in collection.rules)


def get_matching_collections(item: LibraryItem) -> list[Collection]:
    """Return all collections whose rules match the given item."""
    return [
        c for c in list_collections()
        if c.rules and evaluate_collection_rules(c, item)
    ]


# ── add / remove items ─────────────────────────────────────────────────────


def add_item_to_collection(collection_id: str, item_id: str) -> bool:
    collections = _load_collections()
    for c in collections:
        if c["id"] == collection_id:
            if item_id not in c["item_ids"]:
                c["item_ids"].append(item_id)
                c["updated_at"] = datetime.utcnow().isoformat() + "Z"
                _save_collections(collections)
            return True
    return False


def remove_item_from_collection(collection_id: str, item_id: str) -> bool:
    collections = _load_collections()
    for c in collections:
        if c["id"] == collection_id:
            before = len(c["item_ids"])
            c["item_ids"] = [iid for iid in c["item_ids"] if iid != item_id]
            if len(c["item_ids"]) != before:
                c["updated_at"] = datetime.utcnow().isoformat() + "Z"
                _save_collections(collections)
            return True
    return False


# ── Auto-assign collections (re-evaluate all items) ─────────────────────────


def auto_assign_collections(item: LibraryItem) -> list[str]:
    """Run item against all smart collections and return matched collection IDs."""
    matched: list[str] = []
    for col in list_collections():
        if col.rules and evaluate_collection_rules(col, item):
            add_item_to_collection(col.id, item.id)
            matched.append(col.id)
    return matched
