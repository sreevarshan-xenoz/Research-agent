"""
P25: Unit tests for Collaborative Editing endpoints.

Tests cover:
- Yjs WebSocket server manager (health, room lifecycle)
- Section locking API (acquire, release, get, conflict detection, TTL expiry)
- Comment threads API (add, get, resolve, delete, permissions)
- Version history API (create, list, get snapshot, rollback, diff)
"""

from __future__ import annotations

import json
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from research_agent.app.auth import User, current_active_user

# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_collab_state():
    """Reset all module-level collab state between tests."""
    import research_agent.app.collab_routes as cr
    cr._section_locks.clear()
    cr._comments.clear()
    cr._version_snapshots.clear()
    yield
    cr._section_locks.clear()
    cr._comments.clear()
    cr._version_snapshots.clear()


@pytest.fixture
def collab_app():
    """Create a FastAPI app with just the collab router and mocked auth."""
    from research_agent.app.collab_routes import router

    app = FastAPI()
    app.include_router(router)

    mock_user = User(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        email="test@example.com",
        hashed_password="...",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )

    async def mock_current_active_user() -> User:
        return mock_user

    app.dependency_overrides[current_active_user] = mock_current_active_user
    return app


@pytest.fixture
def client(collab_app):
    """FastAPI TestClient with mocked auth."""
    return TestClient(collab_app)


@pytest.fixture
def mock_user_id():
    return "12345678-1234-5678-1234-567812345678"


# ── Helpers ────────────────────────────────────────────────


def _reset_yjs_manager():
    """Reset the Yjs singleton for clean tests."""
    from research_agent.app.yjs_server import reset_yjs_manager
    reset_yjs_manager()


# ════════════════════════════════════════════════════════════
# Section Locking Tests
# ════════════════════════════════════════════════════════════


class TestSectionLocking:
    """Tests for section lock acquire/release and conflict detection."""

    def test_acquire_lock_success(self, client):
        """A user can acquire a lock on a section."""
        resp = client.post("/api/collab/locks/acquire", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["section"] == "introduction"
        assert "token" in data
        assert data["expires_in_seconds"] == 300

    def test_acquire_lock_releases_previous_lock(self, client, mock_user_id):
        """Acquiring a new lock releases the user's previous lock."""
        client.post("/api/collab/locks/acquire", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
        })
        resp2 = client.post("/api/collab/locks/acquire", json={
            "doc_name": "doc-1",
            "section_id": "conclusion",
        })
        assert resp2.status_code == 200
        assert resp2.json()["section"] == "conclusion"

        # Only conclusion should be locked now
        locks_resp = client.get("/api/collab/locks/doc-1")
        assert locks_resp.status_code == 200
        assert "introduction" not in locks_resp.json()["locks"]
        assert "conclusion" in locks_resp.json()["locks"]

    def test_acquire_lock_conflict(self, client):
        """Another user cannot acquire a lock on an already-locked section."""
        # First user acquires
        client.post("/api/collab/locks/acquire", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
        })

        # Second user (different auth) tries
        import research_agent.app.collab_routes as cr
        uid = str(uuid.uuid4())
        doc_locks = cr._section_locks.setdefault("doc-1", {})
        doc_locks["introduction"]["user_id"] = uid

        resp = client.post("/api/collab/locks/acquire", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
        })
        assert resp.status_code == 409
        assert "locked by another user" in resp.json()["detail"]

    def test_release_lock_success(self, client):
        """A user can release their own lock."""
        acq = client.post("/api/collab/locks/acquire", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
        })
        token = acq.json()["token"]

        rel = client.post("/api/collab/locks/release", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
            "lock_token": token,
        })
        assert rel.status_code == 200
        assert rel.json()["success"] is True

        # Verify lock is gone
        locks = client.get("/api/collab/locks/doc-1")
        assert len(locks.json()["locks"]) == 0

    def test_release_lock_no_lock(self, client):
        """Releasing a non-existent lock returns success."""
        resp = client.post("/api/collab/locks/release", json={
            "doc_name": "doc-1",
            "section_id": "nonexistent",
            "lock_token": "fake-token",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_release_lock_wrong_owner(self, client):
        """A non-owner cannot release a lock without the correct token."""
        import research_agent.app.collab_routes as cr
        cr._section_locks.setdefault("doc-1", {})["introduction"] = {
            "user_id": "other-user",
            "locked_at": time.time(),
            "token": "other-token",
        }

        resp = client.post("/api/collab/locks/release", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
            "lock_token": "wrong-token",
        })
        assert resp.status_code == 403

    def test_get_locks_empty(self, client):
        """Getting locks for a doc with no locks returns empty."""
        resp = client.get("/api/collab/locks/doc-empty")
        assert resp.status_code == 200
        assert resp.json()["locks"] == {}
        assert resp.json()["count"] == 0

    def test_get_locks_active(self, client):
        """Getting locks returns active locks with partial user IDs."""
        client.post("/api/collab/locks/acquire", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
        })
        # Same user holds only one lock at a time; acquiring a second releases the first
        client.post("/api/collab/locks/acquire", json={
            "doc_name": "doc-1",
            "section_id": "methodology",
        })

        resp = client.get("/api/collab/locks/doc-1")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        assert "methodology" in resp.json()["locks"]
        assert "introduction" not in resp.json()["locks"]
        for sec_id, lock in resp.json()["locks"].items():
            assert "user_id" in lock
            assert len(lock["user_id"]) == 8  # Truncated
            assert "locked_seconds_ago" in lock

    def test_get_locks_filters_expired(self, client):
        """Expired locks are filtered out of the response."""
        import research_agent.app.collab_routes as cr
        cr._section_locks.setdefault("doc-1", {})["introduction"] = {
            "user_id": "test-user",
            "locked_at": time.time() - 600,  # 10 minutes ago (expired)
            "token": "old-token",
        }

        resp = client.get("/api/collab/locks/doc-1")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_expired_lock_can_be_reacquired(self, client):
        """An expired lock can be acquired by a different user."""
        import research_agent.app.collab_routes as cr
        cr._section_locks.setdefault("doc-1", {})["introduction"] = {
            "user_id": "other-user",
            "locked_at": time.time() - 600,  # Expired
            "token": "old-token",
        }

        resp = client.post("/api/collab/locks/acquire", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ════════════════════════════════════════════════════════════
# Comment Threads Tests
# ════════════════════════════════════════════════════════════


class TestComments:
    """Tests for comment thread CRUD operations."""

    def test_add_comment_success(self, client):
        """A user can add a comment to a section."""
        resp = client.post("/api/collab/comments", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
            "text": "This section needs more citations.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["comment"]["text"] == "This section needs more citations."
        assert data["comment"]["resolved"] is False
        assert "id" in data["comment"]

    def test_add_comment_with_parent(self, client):
        """A comment can be a reply to another comment."""
        parent = client.post("/api/collab/comments", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
            "text": "Parent comment",
        }).json()["comment"]

        resp = client.post("/api/collab/comments", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
            "text": "Reply to parent",
            "parent_id": parent["id"],
        })
        assert resp.status_code == 200
        assert resp.json()["comment"]["parent_id"] == parent["id"]

    def test_get_comments_empty(self, client):
        """Getting comments for a section with no comments returns empty."""
        resp = client.get("/api/collab/comments/doc-1/introduction")
        assert resp.status_code == 200
        assert resp.json()["comments"] == []
        assert resp.json()["count"] == 0

    def test_get_comments_with_data(self, client):
        """Getting comments returns all comments with display names."""
        client.post("/api/collab/comments", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
            "text": "First comment",
        })
        client.post("/api/collab/comments", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
            "text": "Second comment",
        })

        resp = client.get("/api/collab/comments/doc-1/introduction")
        assert resp.status_code == 200
        assert resp.json()["count"] == 2
        for c in resp.json()["comments"]:
            assert "user_display" in c
            assert len(c["user_display"]) == 8

    def test_get_all_comments_summary(self, client):
        """Getting all comments for a doc returns per-section summary."""
        client.post("/api/collab/comments", json={
            "doc_name": "doc-1",
            "section_id": "intro",
            "text": "C1",
        })
        client.post("/api/collab/comments", json={
            "doc_name": "doc-1",
            "section_id": "intro",
            "text": "C2",
        })
        client.post("/api/collab/comments", json={
            "doc_name": "doc-1",
            "section_id": "conclusion",
            "text": "C3",
        })

        resp = client.get("/api/collab/comments/doc-1")
        assert resp.status_code == 200
        assert resp.json()["total"] == 3
        assert resp.json()["unresolved"] == 3
        assert resp.json()["resolved"] == 0
        assert resp.json()["sections"]["intro"]["count"] == 2
        assert resp.json()["sections"]["conclusion"]["count"] == 1

    def test_resolve_comment(self, client):
        """A user can resolve a comment."""
        comment = client.post("/api/collab/comments", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
            "text": "Fix this.",
        }).json()["comment"]

        resp = client.post("/api/collab/comments/resolve", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
            "comment_id": comment["id"],
        })
        assert resp.status_code == 200
        assert resp.json()["comment"]["resolved"] is True
        assert "resolved_by" in resp.json()["comment"]
        assert "resolved_at" in resp.json()["comment"]

    def test_resolve_comment_not_found(self, client):
        """Resolving a non-existent comment returns 404."""
        resp = client.post("/api/collab/comments/resolve", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
            "comment_id": "c-nonexistent",
        })
        assert resp.status_code == 404

    def test_delete_own_comment(self, client, mock_user_id):
        """A user can delete their own comment."""
        comment = client.post("/api/collab/comments", json={
            "doc_name": "doc-1",
            "section_id": "introduction",
            "text": "Delete me.",
        }).json()["comment"]

        resp = client.delete(
            f"/api/collab/comments/doc-1/introduction/{comment['id']}"
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify it's gone
        get_resp = client.get("/api/collab/comments/doc-1/introduction")
        assert get_resp.json()["count"] == 0

    def test_delete_someone_elses_comment_returns_403(self, client):
        """A user cannot delete another user's comment (non-admin)."""
        import research_agent.app.collab_routes as cr
        cr._comments.setdefault("doc-1", {}).setdefault("intro", []).append({
            "id": "c-other",
            "user_id": "other-user-id",
            "text": "Someone else's comment",
            "created_at": time.time(),
            "resolved": False,
            "parent_id": None,
        })

        resp = client.delete("/api/collab/comments/doc-1/intro/c-other")
        assert resp.status_code == 403

    def test_delete_nonexistent_comment(self, client):
        """Deleting a non-existent comment returns 404."""
        resp = client.delete("/api/collab/comments/doc-1/intro/c-fake")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════
# Version History Tests
# ════════════════════════════════════════════════════════════


class TestVersionHistory:
    """Tests for version snapshot creation, listing, and rollback."""

    def test_create_snapshot(self, client):
        """A user can create a version snapshot."""
        resp = client.post("/api/collab/versions", json={
            "doc_name": "doc-1",
            "label": "First draft",
            "content": "\\section{Intro}\nContent here.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["snapshot"]["label"] == "First draft"
        assert "id" in data["snapshot"]

    def test_create_snapshot_auto_label(self, client):
        """Creating a snapshot without a label generates one automatically."""
        resp = client.post("/api/collab/versions", json={
            "doc_name": "doc-1",
            "label": "",
            "content": "Content",
        })
        assert resp.status_code == 200
        label = resp.json()["snapshot"]["label"]
        assert label.startswith("Snapshot ")

    def test_list_snapshots_empty(self, client):
        """Listing snapshots for a doc with none returns empty."""
        resp = client.get("/api/collab/versions/doc-empty")
        assert resp.status_code == 200
        assert resp.json()["snapshots"] == []
        assert resp.json()["count"] == 0

    def test_list_snapshots_most_recent_first(self, client):
        """Snapshots are listed most recent first."""
        client.post("/api/collab/versions", json={
            "doc_name": "doc-1",
            "label": "V1",
            "content": "Version 1",
        })
        client.post("/api/collab/versions", json={
            "doc_name": "doc-1",
            "label": "V2",
            "content": "Version 2",
        })

        resp = client.get("/api/collab/versions/doc-1")
        assert resp.status_code == 200
        assert resp.json()["count"] == 2
        # Most recent first
        assert resp.json()["snapshots"][0]["label"] == "V2"
        assert resp.json()["snapshots"][1]["label"] == "V1"

    def test_get_specific_snapshot(self, client):
        """Getting a specific snapshot returns its full content."""
        created = client.post("/api/collab/versions", json={
            "doc_name": "doc-1",
            "label": "My Snapshot",
            "content": "Full content here.",
        }).json()["snapshot"]
        sid = created["id"]

        resp = client.get(f"/api/collab/versions/doc-1/{sid}")
        assert resp.status_code == 200
        assert resp.json()["snapshot"]["content"] == "Full content here."
        assert resp.json()["snapshot"]["label"] == "My Snapshot"

    def test_get_snapshot_not_found(self, client):
        """Getting a non-existent snapshot returns 404."""
        resp = client.get("/api/collab/versions/doc-1/v-fake")
        assert resp.status_code == 404

    def test_rollback_snapshot(self, client):
        """Rolling back to a snapshot returns its content."""
        created = client.post("/api/collab/versions", json={
            "doc_name": "doc-1",
            "label": "Rollback target",
            "content": "Rollback content",
        }).json()["snapshot"]

        resp = client.post("/api/collab/versions/rollback", json={
            "doc_name": "doc-1",
            "snapshot_id": created["id"],
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["snapshot"]["content"] == "Rollback content"
        assert "rolled_back_at" in resp.json()["snapshot"]

    def test_rollback_snapshot_not_found(self, client):
        """Rolling back to a non-existent snapshot returns 404."""
        resp = client.post("/api/collab/versions/rollback", json={
            "doc_name": "doc-1",
            "snapshot_id": "v-fake",
        })
        assert resp.status_code == 404

    def test_version_diff(self, client):
        """Getting a diff between two snapshots works."""
        v1 = client.post("/api/collab/versions", json={
            "doc_name": "doc-1",
            "label": "Before",
            "content": "Line 1\nLine 2\nLine 3",
        }).json()["snapshot"]

        v2 = client.post("/api/collab/versions", json={
            "doc_name": "doc-1",
            "label": "After",
            "content": "Line 1\nLine 2 modified\nLine 4",
        }).json()["snapshot"]

        resp = client.get(
            f"/api/collab/versions/diff/doc-1?"
            f"from_snapshot={v1['id']}&to_snapshot={v2['id']}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["from"] == v1["id"]
        assert data["to"] == v2["id"]
        assert data["additions"] >= 1
        assert data["removals"] >= 1

    def test_version_diff_snapshot_not_found(self, client):
        """Getting diff with non-existent snapshots returns 404."""
        resp = client.get(
            "/api/collab/versions/diff/doc-1?"
            "from_snapshot=v-fake&to_snapshot=v-fake2"
        )
        assert resp.status_code == 404

    def test_snapshot_limit_50(self, client):
        """Only the most recent 50 snapshots are kept per document."""
        for i in range(55):
            client.post("/api/collab/versions", json={
                "doc_name": "doc-1",
                "label": f"V{i}",
                "content": f"Version {i}",
            })

        resp = client.get("/api/collab/versions/doc-1")
        assert resp.json()["count"] == 50
        # The oldest (V0) should be gone
        labels = [s["label"] for s in resp.json()["snapshots"]]
        assert "V0" not in labels
        assert "V54" in labels

    def test_snapshot_includes_content_length(self, client):
        """List response includes content_length metadata."""
        client.post("/api/collab/versions", json={
            "doc_name": "doc-1",
            "label": "Test",
            "content": "A" * 100,
        })

        resp = client.get("/api/collab/versions/doc-1")
        assert resp.json()["snapshots"][0]["content_length"] == 100


# ════════════════════════════════════════════════════════════
# Yjs Server Manager Tests
# ════════════════════════════════════════════════════════════


class TestYjsServerManager:
    """Tests for the YjsServerManager class (room management, health)."""

    def setup_method(self):
        _reset_yjs_manager()

    def test_get_health_default(self):
        """Health endpoint returns basic server info."""
        from research_agent.app.yjs_server import get_yjs_manager
        mgr = get_yjs_manager()
        health = mgr.get_health()
        assert "yjs_available" in health  # May be False if y-py not installed
        assert "rooms" in health
        assert "total_clients" in health
        assert "persist_dir" in health

    def test_get_or_create_room(self):
        """Getting a room creates it if it doesn't exist."""
        from research_agent.app.yjs_server import get_yjs_manager
        mgr = get_yjs_manager()
        room = mgr.get_or_create_room("test-doc")
        assert room.client_count == 0
        assert "test-doc" in mgr.rooms

    def test_get_or_create_room_reuses_existing(self):
        """Getting the same room returns the existing instance."""
        from research_agent.app.yjs_server import get_yjs_manager
        mgr = get_yjs_manager()
        room1 = mgr.get_or_create_room("test-doc")
        room2 = mgr.get_or_create_room("test-doc")
        assert room1 is room2

    def test_remove_empty_rooms(self):
        """Empty rooms with no activity are cleaned up."""
        from research_agent.app.yjs_server import get_yjs_manager
        mgr = get_yjs_manager()
        mgr.get_or_create_room("old-doc")
        mgr.get_or_create_room("new-doc")

        # Mark old-doc as inactive
        mgr.rooms["old-doc"].last_activity = time.time() - 7200  # 2 hours

        removed = mgr.remove_empty_rooms(older_than_seconds=3600)
        assert removed == 1
        assert "old-doc" not in mgr.rooms
        assert "new-doc" in mgr.rooms

    def test_active_rooms_not_removed(self):
        """Active empty rooms are not removed."""
        from research_agent.app.yjs_server import get_yjs_manager
        mgr = get_yjs_manager()
        mgr.get_or_create_room("active-doc")
        removed = mgr.remove_empty_rooms(older_than_seconds=3600)
        assert removed == 0
        assert "active-doc" in mgr.rooms

    def test_get_awareness_state_no_room(self):
        """Getting awareness for a non-existent room returns empty."""
        from research_agent.app.yjs_server import get_yjs_manager
        mgr = get_yjs_manager()
        assert mgr.get_awareness_state("nonexistent") == []

    def test_reset_yjs_manager(self):
        """Reset clears the singleton."""
        from research_agent.app.yjs_server import get_yjs_manager, reset_yjs_manager
        mgr1 = get_yjs_manager()
        mgr1.get_or_create_room("test")
        reset_yjs_manager()
        mgr2 = get_yjs_manager()
        # After reset, the manager is a new instance with no rooms
        assert mgr2 is not mgr1
        assert mgr2.get_health()["rooms"] == 0


# ════════════════════════════════════════════════════════════
# Collab Status / Health Tests
# ════════════════════════════════════════════════════════════


class TestCollabStatus:
    """Tests for the collaboration system status endpoint."""

    def test_status_returns_metrics(self, client):
        """Status endpoint returns collab system metrics."""
        resp = client.get("/api/collab/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "yjs_server" in data
        assert "section_locks" in data
        assert "comments" in data
        assert "version_snapshots" in data

    def test_status_reflects_activity(self, client):
        """Status metrics reflect actual activity."""
        # Add some data
        client.post("/api/collab/locks/acquire", json={
            "doc_name": "doc-1",
            "section_id": "intro",
        })
        client.post("/api/collab/comments", json={
            "doc_name": "doc-1",
            "section_id": "intro",
            "text": "A comment",
        })
        client.post("/api/collab/versions", json={
            "doc_name": "doc-1",
            "label": "V1",
            "content": "Content",
        })

        resp = client.get("/api/collab/status")
        data = resp.json()
        assert data["section_locks"]["total_locked"] >= 1
        assert data["comments"]["total"] >= 1
        assert data["version_snapshots"]["total"] >= 1


# ════════════════════════════════════════════════════════════
# Integration: Full Workflow Tests
# ════════════════════════════════════════════════════════════


class TestCollabWorkflow:
    """End-to-end workflow tests covering realistic scenarios."""

    def test_lock_comment_snapshot_workflow(self, client):
        """A realistic workflow: lock section → add comment → create snapshot."""
        # 1. Lock a section
        lock = client.post("/api/collab/locks/acquire", json={
            "doc_name": "doc-workflow",
            "section_id": "methodology",
        })
        assert lock.status_code == 200
        token = lock.json()["token"]

        # 2. Add comments while editing
        c1 = client.post("/api/collab/comments", json={
            "doc_name": "doc-workflow",
            "section_id": "methodology",
            "text": "Need to add statistical tests here.",
        })
        assert c1.status_code == 200

        c2 = client.post("/api/collab/comments", json={
            "doc_name": "doc-workflow",
            "section_id": "methodology",
            "text": "Check sample size justification.",
        })
        assert c2.status_code == 200

        # 3. Create a snapshot before making changes
        snap = client.post("/api/collab/versions", json={
            "doc_name": "doc-workflow",
            "label": "Before statistical tests",
            "content": "\\section{Methodology}\nStandard deviation...",
        })
        assert snap.status_code == 200
        snap_id = snap.json()["snapshot"]["id"]

        # 4. Verify snapshot was created
        snap_get = client.get(f"/api/collab/versions/doc-workflow/{snap_id}")
        assert snap_get.status_code == 200

        # 5. Create a second snapshot (updated version)
        snap2 = client.post("/api/collab/versions", json={
            "doc_name": "doc-workflow",
            "label": "After adding tests",
            "content": "\\section{Methodology}\nStandard deviation...\\n\\subsection{Statistical Tests}\nANOVA...",
        })
        assert snap2.status_code == 200

        # 6. Get a diff between the two snapshots
        diff = client.get(
            f"/api/collab/versions/diff/doc-workflow?"
            f"from_snapshot={snap_id}&to_snapshot={snap2.json()['snapshot']['id']}"
        )
        assert diff.status_code == 200
        assert diff.json()["additions"] >= 1

        # 7. Rollback to first snapshot
        rollback = client.post("/api/collab/versions/rollback", json={
            "doc_name": "doc-workflow",
            "snapshot_id": snap_id,
        })
        assert rollback.status_code == 200

        # 8. Release the lock
        release = client.post("/api/collab/locks/release", json={
            "doc_name": "doc-workflow",
            "section_id": "methodology",
            "lock_token": token,
        })
        assert release.status_code == 200

        # 9. Verify lock released
        locks = client.get("/api/collab/locks/doc-workflow")
        assert locks.json()["count"] == 0

        # 10. Resolve a comment
        resp = client.get("/api/collab/comments/doc-workflow/methodology")
        comment_id = resp.json()["comments"][0]["id"]

        resolve = client.post("/api/collab/comments/resolve", json={
            "doc_name": "doc-workflow",
            "section_id": "methodology",
            "comment_id": comment_id,
        })
        assert resolve.status_code == 200
        assert resolve.json()["comment"]["resolved"] is True
