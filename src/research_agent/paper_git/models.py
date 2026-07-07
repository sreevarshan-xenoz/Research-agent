"""P36: Paper-git — Data models for version control on research documents."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DiffKind(str, Enum):
    """Types of changes in a diff."""
    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"
    UNCHANGED = "unchanged"


class DiffHunk(BaseModel):
    """A single contiguous change region within a file."""
    kind: DiffKind
    old_start: int = 0       # line number in old version (0-indexed)
    old_end: int = 0
    new_start: int = 0       # line number in new version
    new_end: int = 0
    content: str = ""        # the changed text
    old_content: str = ""    # the original text (for modification / deletion)


class FileDiff(BaseModel):
    """Diff for a single file."""
    file_path: str           # e.g. "main.tex", "references.bib"
    hunks: list[DiffHunk] = Field(default_factory=list)
    old_hash: str = ""       # sha256 of old version
    new_hash: str = ""       # sha256 of new version


class DiffResult(BaseModel):
    """Complete diff result between two snapshots."""
    old_snapshot_id: str
    new_snapshot_id: str
    files: list[FileDiff] = Field(default_factory=list)
    summary: str = ""         # human-readable summary
    stat_additions: int = 0
    stat_deletions: int = 0
    stat_files_changed: int = 0


class SnapshotFile(BaseModel):
    """Metadata + content for a single file in a snapshot."""
    path: str
    content: str
    content_hash: str = ""


class Snapshot(BaseModel):
    """A point-in-time snapshot of a research run's artifacts."""
    id: str
    run_id: str              # FK to the research run
    branch: str = "main"     # branch name
    parent_id: str | None = None  # previous snapshot in this branch
    message: str = ""        # commit message
    author: str = ""         # who created this snapshot
    files: list[SnapshotFile] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)  # e.g. ["draft", "submitted", "reviewed"]
    created_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Branch(BaseModel):
    """A named line of development."""
    id: str
    name: str
    head_snapshot_id: str    # latest snapshot on this branch
    base_branch: str = "main"
    created_at: str = ""
    updated_at: str = ""
    description: str = ""
    is_protected: bool = False  # prevent force-deletion


class MergeConflict(BaseModel):
    """A single conflict during a 3-way merge."""
    file_path: str
    hunk_index: int
    base_content: str = ""
    ours_content: str = ""
    theirs_content: str = ""
    resolution: str = ""     # resolved text (empty if unresolved)
    resolved: bool = False


class MergeResult(BaseModel):
    """Result of attempting a merge."""
    success: bool
    conflict_count: int = 0
    conflicts: list[MergeConflict] = Field(default_factory=list)
    merged_snapshot_id: str = ""
    message: str = ""


class PRStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    MERGED = "merged"
    CLOSED = "closed"


class PRComment(BaseModel):
    """A review comment on a PR."""
    id: str
    author: str
    body: str
    file_path: str = ""      # empty = general comment
    line_start: int = 0
    line_end: int = 0
    created_at: str = ""
    resolved: bool = False


class PullRequest(BaseModel):
    """A pull request / merge proposal."""
    id: str
    title: str
    description: str = ""
    author: str = ""
    source_branch: str
    target_branch: str = "main"
    status: PRStatus = PRStatus.OPEN
    snapshot_id: str = ""    # the snapshot to merge
    base_snapshot_id: str = ""
    comments: list[PRComment] = Field(default_factory=list)
    approvals: list[str] = Field(default_factory=list)  # list of approvers
    created_at: str = ""
    updated_at: str = ""
    merged_at: str | None = None
    merged_by: str | None = None
    conflict_report: str = ""


class CheckpointRestore(BaseModel):
    """Records a restore operation — restoring from a snapshot."""
    id: str
    snapshot_id: str
    run_id: str
    restored_at: str = ""
    restored_by: str = ""
    note: str = ""
