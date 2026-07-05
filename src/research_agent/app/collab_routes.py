"""
P25: Collaborative Real-Time Co-Editing Routes

API endpoints for:
- Yjs WebSocket sync protocol (CRDT-based co-editing)
- Per-section locking and conflict resolution
- Comment threads on paper sections
- Version history with diff viewer and rollback

All read-only endpoints are auth-free to support iframe embedding.
Mutation endpoints require authentication.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from pydantic import BaseModel

from research_agent.app.auth import User, current_active_user

logger = logging.getLogger(__name__)

# ── Router ────────────────────────────────────────────────────
router = APIRouter(prefix="/api/collab", tags=["collaboration"])

# ── In-memory stores ─────────────────────────────────────────
# (Persisted to filesystem for recovery)
_COLLAB_DATA_DIR = Path(".runtime/collab")
_COLLAB_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Section locks: {doc_name: {section_id: {"user_id": ..., "locked_at": ...}}}
_section_locks: dict[str, dict[str, dict[str, Any]]] = {}

# Comments: {doc_name: {section_id: [comment, ...]}}
_comments: dict[str, dict[str, list[dict[str, Any]]]] = {}

# Version snapshots: {doc_name: [snapshot, ...]}
_version_snapshots: dict[str, list[dict[str, Any]]] = {}


def _load_json(path: Path) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def _load_locks() -> None:
    global _section_locks
    data = _load_json(_COLLAB_DATA_DIR / "locks.json")
    if data is not None:
        _section_locks = data


def _save_locks() -> None:
    _save_json(_COLLAB_DATA_DIR / "locks.json", _section_locks)


def _load_comments() -> None:
    global _comments
    data = _load_json(_COLLAB_DATA_DIR / "comments.json")
    if data is not None:
        _comments = data


def _save_comments() -> None:
    _save_json(_COLLAB_DATA_DIR / "comments.json", _comments)


def _load_snapshots() -> None:
    global _version_snapshots
    data = _load_json(_COLLAB_DATA_DIR / "snapshots.json")
    if data is not None:
        _version_snapshots = data


def _save_snapshots() -> None:
    _save_json(_COLLAB_DATA_DIR / "snapshots.json", _version_snapshots)


# Load persisted state on import
_load_locks()
_load_comments()
_load_snapshots()


# ══════════════════════════════════════════════════════════════
# Yjs WebSocket Endpoint
# ══════════════════════════════════════════════════════════════


@router.websocket("/ws/{doc_name}")
async def collab_websocket(ws: WebSocket, doc_name: str):
    """WebSocket endpoint for Yjs collaborative editing sync protocol.

    Delegates to the YjsServerManager which handles the Yjs sync
    protocol (sync step1/step2), awareness (cursor presence), and
    update broadcasting to all connected clients in the room.

    Doc_name identifies the document room (e.g. "run-abc123").
    """
    from research_agent.app.yjs_server import get_yjs_manager
    manager = get_yjs_manager()
    await manager.handle_websocket(ws, doc_name)


# ══════════════════════════════════════════════════════════════
# Section Locking API
# ══════════════════════════════════════════════════════════════


class LockRequest(BaseModel):
    doc_name: str
    section_id: str


class UnlockRequest(BaseModel):
    doc_name: str
    section_id: str
    lock_token: str


@router.post("/locks/acquire")
async def acquire_lock(
    req: LockRequest,
    user: User = Depends(current_active_user),
):
    """Acquire an exclusive lock on a paper section.

    A user can only hold one lock at a time across all sections.
    Returns the lock token and expiry.
    """
    uid = str(user.id)
    doc = req.doc_name
    section = req.section_id

    doc_locks = _section_locks.setdefault(doc, {})

    # Check if already locked by another user
    existing = doc_locks.get(section)
    if existing and existing["user_id"] != uid:
        # Check if lock expired (5 minute TTL)
        age = time.time() - existing["locked_at"]
        if age < 300:  # 5 minutes
            raise HTTPException(
                status_code=409,
                detail=f"Section locked by another user since {age:.0f}s ago",
            )

    # Release previous locks held by this user
    for sec_id, lock in list(doc_locks.items()):
        if lock["user_id"] == uid and sec_id != section:
            del doc_locks[sec_id]

    # Acquire the lock
    lock_token = str(uuid.uuid4())
    doc_locks[section] = {
        "user_id": uid,
        "locked_at": time.time(),
        "token": lock_token,
    }
    _save_locks()

    return {
        "success": True,
        "section": section,
        "token": lock_token,
        "expires_in_seconds": 300,
        "locked_by": uid,
    }


@router.post("/locks/release")
async def release_lock(
    req: UnlockRequest,
    user: User = Depends(current_active_user),
):
    """Release a section lock."""
    uid = str(user.id)
    doc_locks = _section_locks.get(req.doc_name, {})
    lock = doc_locks.get(req.section_id)

    if not lock:
        return {"success": True, "message": "No lock to release"}

    if lock["user_id"] != uid and lock.get("token") != req.lock_token:
        raise HTTPException(status_code=403, detail="Not the lock owner")

    del doc_locks[req.section_id]
    _save_locks()
    return {"success": True, "section": req.section_id}


@router.get("/locks/{doc_name}")
async def get_locks(doc_name: str):
    """Get all active locks for a document."""
    doc_locks = _section_locks.get(doc_name, {})

    # Filter expired locks
    now = time.time()
    active = {}
    for sec_id, lock in doc_locks.items():
        if now - lock["locked_at"] < 300:
            active[sec_id] = {
                "user_id": lock["user_id"][:8],  # Partial for privacy
                "locked_at": lock["locked_at"],
                "locked_seconds_ago": round(now - lock["locked_at"], 1),
            }

    return {"locks": active, "count": len(active)}


# ══════════════════════════════════════════════════════════════
# Comment Threads API
# ══════════════════════════════════════════════════════════════


class AddCommentRequest(BaseModel):
    doc_name: str
    section_id: str
    text: str
    parent_id: str | None = None  # For replies


class ResolveCommentRequest(BaseModel):
    doc_name: str
    section_id: str
    comment_id: str


@router.post("/comments")
async def add_comment(
    req: AddCommentRequest,
    user: User = Depends(current_active_user),
):
    """Add a comment to a paper section."""
    uid = str(user.id)
    doc = req.doc_name
    section = req.section_id

    comment = {
        "id": f"c-{uuid.uuid4().hex[:8]}",
        "user_id": uid,
        "text": req.text,
        "created_at": time.time(),
        "resolved": False,
        "parent_id": req.parent_id,
    }

    doc_comments = _comments.setdefault(doc, {})
    section_comments = doc_comments.setdefault(section, [])
    section_comments.append(comment)
    _save_comments()

    return {"success": True, "comment": comment}


@router.get("/comments/{doc_name}/{section_id}")
async def get_comments(doc_name: str, section_id: str):
    """Get all comments for a paper section."""
    doc_comments = _comments.get(doc_name, {})
    section_comments = doc_comments.get(section_id, [])

    # Add user display name (truncated user ID)
    result = []
    for c in section_comments:
        result.append({
            **c,
            "user_display": c.get("user_id", "")[:8],
        })

    return {"comments": result, "count": len(result)}


@router.get("/comments/{doc_name}")
async def get_all_comments(doc_name: str):
    """Get all comments across all sections for a document."""
    doc_comments = _comments.get(doc_name, {})

    # Summarize per-section
    sections = {}
    total = 0
    unresolved = 0
    for sec_id, comments in doc_comments.items():
        sections[sec_id] = {
            "count": len(comments),
            "unresolved": sum(1 for c in comments if not c["resolved"]),
            "latest": comments[-1] if comments else None,
        }
        total += len(comments)
        unresolved += sections[sec_id]["unresolved"]

    return {
        "sections": sections,
        "total": total,
        "unresolved": unresolved,
        "resolved": total - unresolved,
    }


@router.post("/comments/resolve")
async def resolve_comment(
    req: ResolveCommentRequest,
    user: User = Depends(current_active_user),
):
    """Mark a comment as resolved."""
    doc_comments = _comments.get(req.doc_name, {})
    section_comments = doc_comments.get(req.section_id, [])

    for c in section_comments:
        if c["id"] == req.comment_id:
            c["resolved"] = True
            c["resolved_by"] = str(user.id)
            c["resolved_at"] = time.time()
            _save_comments()
            return {"success": True, "comment": c}

    raise HTTPException(status_code=404, detail="Comment not found")


@router.delete("/comments/{doc_name}/{section_id}/{comment_id}")
async def delete_comment(
    doc_name: str,
    section_id: str,
    comment_id: str,
    user: User = Depends(current_active_user),
):
    """Delete a comment (own comment or admin)."""
    uid = str(user.id)
    doc_comments = _comments.get(doc_name, {})
    section_comments = doc_comments.get(section_id, [])

    for i, c in enumerate(section_comments):
        if c["id"] == comment_id:
            if c["user_id"] != uid:
                from research_agent.app.security import is_admin
                if not is_admin(user):
                    raise HTTPException(status_code=403, detail="Not your comment")
            del section_comments[i]
            _save_comments()
            return {"success": True}

    raise HTTPException(status_code=404, detail="Comment not found")


# ══════════════════════════════════════════════════════════════
# Version History API
# ══════════════════════════════════════════════════════════════


class CreateSnapshotRequest(BaseModel):
    doc_name: str
    label: str = ""  # Optional user-provided label
    content: str  # Full document content (LaTeX or serialized Ydoc)


class RollbackRequest(BaseModel):
    doc_name: str
    snapshot_id: str


@router.post("/versions")
async def create_snapshot(
    req: CreateSnapshotRequest,
    user: User = Depends(current_active_user),
):
    """Create a named snapshot/checkpoint of a document."""
    snapshot = {
        "id": f"v-{uuid.uuid4().hex[:8]}",
        "doc_name": req.doc_name,
        "label": req.label or f"Snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "content": req.content,
        "created_at": time.time(),
        "created_by": str(user.id),
    }

    doc_snapshots = _version_snapshots.setdefault(req.doc_name, [])
    doc_snapshots.append(snapshot)

    # Keep max 50 snapshots per document
    if len(doc_snapshots) > 50:
        doc_snapshots.pop(0)

    _save_snapshots()
    return {"success": True, "snapshot": {
        "id": snapshot["id"],
        "label": snapshot["label"],
        "created_at": snapshot["created_at"],
    }}


@router.get("/versions/{doc_name}")
async def list_snapshots(doc_name: str):
    """List all snapshots for a document."""
    doc_snapshots = _version_snapshots.get(doc_name, [])

    return {
        "snapshots": [
            {
                "id": s["id"],
                "label": s["label"],
                "created_at": s["created_at"],
                "created_by": s.get("created_by", "")[:8],
                "content_length": len(s.get("content", "")),
            }
            for s in reversed(doc_snapshots)  # Most recent first
        ],
        "count": len(doc_snapshots),
    }


@router.get("/versions/{doc_name}/{snapshot_id}")
async def get_snapshot(doc_name: str, snapshot_id: str):
    """Get a specific snapshot with full content."""
    doc_snapshots = _version_snapshots.get(doc_name, [])

    for s in doc_snapshots:
        if s["id"] == snapshot_id:
            return {
                "snapshot": {
                    "id": s["id"],
                    "label": s["label"],
                    "created_at": s["created_at"],
                    "content": s["content"],
                }
            }

    raise HTTPException(status_code=404, detail="Snapshot not found")


@router.post("/versions/rollback")
async def rollback_snapshot(
    req: RollbackRequest,
    user: User = Depends(current_active_user),
):
    """Rollback a document to a previous snapshot.

    Returns the snapshot content for the client to apply.
    This is a soft rollback — the client uses this content
    to overwrite the Yjs document state.
    """
    doc_snapshots = _version_snapshots.get(req.doc_name, [])

    for s in doc_snapshots:
        if s["id"] == req.snapshot_id:
            return {
                "success": True,
                "snapshot": {
                    "id": s["id"],
                    "label": s["label"],
                    "content": s["content"],
                    "rolled_back_at": time.time(),
                },
            }

    raise HTTPException(status_code=404, detail="Snapshot not found")


@router.get("/versions/diff/{doc_name}")
async def get_version_diff(
    doc_name: str,
    from_snapshot: str,
    to_snapshot: str,
):
    """Get a simple line-based diff between two snapshots (no auth)."""
    doc_snapshots = _version_snapshots.get(doc_name, [])
    from_content = None
    to_content = None

    for s in doc_snapshots:
        if s["id"] == from_snapshot:
            from_content = s["content"]
        if s["id"] == to_snapshot:
            to_content = s["content"]

    if from_content is None or to_content is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Simple line diff
    from_lines = from_content.splitlines()
    to_lines = to_content.splitlines()

    additions = []
    removals = []
    max_lines = max(len(from_lines), len(to_lines))

    for i in range(max_lines):
        from_line = from_lines[i] if i < len(from_lines) else ""
        to_line = to_lines[i] if i < len(to_lines) else ""

        if from_line != to_line:
            if from_line and from_line != to_line:
                removals.append({"line": i + 1, "text": from_line})
            if to_line:
                additions.append({"line": i + 1, "text": to_line})

    return {
        "from": from_snapshot,
        "to": to_snapshot,
        "additions": len(additions),
        "removals": len(removals),
        "additions_detail": additions[:50],  # Cap at 50 lines
        "removals_detail": removals[:50],
    }


# ══════════════════════════════════════════════════════════════
# Collaboration Status (Health)
# ══════════════════════════════════════════════════════════════


@router.get("/status")
async def collab_status():
    """Get collaborative editing system status."""
    from research_agent.app.yjs_server import get_yjs_manager
    yjs = get_yjs_manager()
    yjs_health = yjs.get_health()

    return {
        "yjs_server": yjs_health,
        "section_locks": {
            "total_locked": sum(len(locks) for locks in _section_locks.values()),
            "documents": len(_section_locks),
        },
        "comments": {
            "total": sum(
                len(comments)
                for doc in _comments.values()
                for comments in doc.values()
            ),
            "documents": len(_comments),
        },
        "version_snapshots": {
            "total": sum(len(ss) for ss in _version_snapshots.values()),
            "documents": len(_version_snapshots),
        },
    }
