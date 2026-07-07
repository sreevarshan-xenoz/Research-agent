"""P36: Paper-git — Snapshot/version storage with JSON persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from research_agent.paper_git.models import (
    Branch,
    PullRequest,
    PRStatus,
    Snapshot,
    SnapshotFile,
    CheckpointRestore,
)


def _store_root() -> Path:
    p = Path(".runtime/paper_git")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _snapshots_path() -> Path:
    return _store_root() / "snapshots.json"


def _branches_path() -> Path:
    return _store_root() / "branches.json"


def _prs_path() -> Path:
    return _store_root() / "pull_requests.json"


def _restores_path() -> Path:
    return _store_root() / "restores.json"


# ── JSON helpers ───────────────────────────────────────────────────────────


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw) if raw.strip() else []


def _save_json(path: Path, data: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ── Snapshot CRUD ──────────────────────────────────────────────────────────


def list_snapshots(run_id: str | None = None, branch: str | None = None) -> list[Snapshot]:
    all_s = _load_json(_snapshots_path())
    if run_id:
        all_s = [s for s in all_s if s.get("run_id") == run_id]
    if branch:
        all_s = [s for s in all_s if s.get("branch") == branch]
    all_s.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return [Snapshot(**s) for s in all_s]


def get_snapshot(snapshot_id: str) -> Snapshot | None:
    for s in _load_json(_snapshots_path()):
        if s["id"] == snapshot_id:
            return Snapshot(**s)
    return None


def create_snapshot(
    run_id: str,
    branch: str = "main",
    message: str = "",
    author: str = "",
    files: list[SnapshotFile] | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    parent_id: str | None = None,
) -> Snapshot:
    snapshots = _load_json(_snapshots_path())
    now = datetime.utcnow().isoformat() + "Z"

    # Compute content hashes for files
    for f in (files or []):
        if not f.content_hash:
            f.content_hash = hashlib.sha256(f.content.encode("utf-8")).hexdigest()[:16]

    snapshot = Snapshot(
        id=f"snap-{uuid4().hex[:12]}",
        run_id=run_id,
        branch=branch,
        parent_id=parent_id,
        message=message,
        author=author,
        files=files or [],
        tags=tags or [],
        created_at=now,
        metadata=metadata or {},
    )
    snapshots.append(snapshot.model_dump())
    _save_json(_snapshots_path(), snapshots)

    # Update branch head
    _update_branch_head(branch, snapshot.id)

    return snapshot


def _update_branch_head(branch_name: str, snapshot_id: str) -> None:
    branches = _load_json(_branches_path())
    for b in branches:
        if b["name"] == branch_name:
            b["head_snapshot_id"] = snapshot_id
            b["updated_at"] = datetime.utcnow().isoformat() + "Z"
            _save_json(_branches_path(), branches)
            return

    # Branch doesn't exist yet — create it
    now = datetime.utcnow().isoformat() + "Z"
    branch = Branch(
        id=f"branch-{uuid4().hex[:8]}",
        name=branch_name,
        head_snapshot_id=snapshot_id,
        base_branch="main",
        created_at=now,
        updated_at=now,
    )
    branches.append(branch.model_dump())
    _save_json(_branches_path(), branches)


def delete_snapshot(snapshot_id: str) -> bool:
    snapshots = _load_json(_snapshots_path())
    before = len(snapshots)
    snapshots = [s for s in snapshots if s["id"] != snapshot_id]
    if len(snapshots) == before:
        return False
    _save_json(_snapshots_path(), snapshots)
    return True


# ── Branch CRUD ────────────────────────────────────────────────────────────


def list_branches() -> list[Branch]:
    return [Branch(**b) for b in _load_json(_branches_path())]


def get_branch(name: str) -> Branch | None:
    for b in _load_json(_branches_path()):
        if b["name"] == name:
            return Branch(**b)
    return None


def create_branch(
    name: str,
    from_snapshot_id: str,
    description: str = "",
) -> Branch:
    existing = get_branch(name)
    if existing:
        raise ValueError(f"Branch '{name}' already exists")

    branches = _load_json(_branches_path())
    now = datetime.utcnow().isoformat() + "Z"
    branch = Branch(
        id=f"branch-{uuid4().hex[:8]}",
        name=name,
        head_snapshot_id=from_snapshot_id,
        base_branch="main",
        created_at=now,
        updated_at=now,
        description=description,
    )
    branches.append(branch.model_dump())
    _save_json(_branches_path(), branches)

    # Find the parent snapshot's run_id for the first snapshot on the new branch
    parent = get_snapshot(from_snapshot_id)
    if parent:
        create_snapshot(
            run_id=parent.run_id,
            branch=name,
            message=f"Branch '{name}' created from snapshot {from_snapshot_id[:12]}",
            author="system",
            files=parent.files,
            tags=parent.tags,
            parent_id=from_snapshot_id,
        )
    return branch


def delete_branch(name: str) -> bool:
    branches = _load_json(_branches_path())
    before = len(branches)
    branches = [b for b in branches if b["name"] != name]
    if len(branches) == before:
        return False
    _save_json(_branches_path(), branches)
    return True


# ── Pull Request CRUD ─────────────────────────────────────────────────────


def list_pull_requests(status: PRStatus | None = None) -> list[PullRequest]:
    all_prs = _load_json(_prs_path())
    if status:
        all_prs = [pr for pr in all_prs if pr.get("status") == status.value]
    all_prs.sort(key=lambda pr: pr.get("updated_at", ""), reverse=True)
    return [PullRequest(**pr) for pr in all_prs]


def get_pull_request(pr_id: str) -> PullRequest | None:
    for pr in _load_json(_prs_path()):
        if pr["id"] == pr_id:
            return PullRequest(**pr)
    return None


def create_pull_request(
    title: str,
    source_branch: str,
    target_branch: str = "main",
    author: str = "",
    description: str = "",
) -> PullRequest:
    prs = _load_json(_prs_path())
    now = datetime.utcnow().isoformat() + "Z"
    source_b = get_branch(source_branch)
    target_branch_obj = get_branch(target_branch)
    if not source_b:
        raise ValueError(f"Source branch '{source_branch}' not found")
    if not target_branch_obj:
        raise ValueError(f"Target branch '{target_branch}' not found")

    pr = PullRequest(
        id=f"pr-{uuid4().hex[:8]}",
        title=title,
        description=description,
        author=author,
        source_branch=source_branch,
        target_branch=target_branch,
        status=PRStatus.OPEN,
        snapshot_id=source_b.head_snapshot_id,
        base_snapshot_id=target_branch_obj.head_snapshot_id,
        created_at=now,
        updated_at=now,
    )
    prs.append(pr.model_dump())
    _save_json(_prs_path(), prs)
    return pr


def update_pull_request(pr_id: str, updates: dict[str, Any]) -> PullRequest | None:
    prs = _load_json(_prs_path())
    for pr in prs:
        if pr["id"] == pr_id:
            pr.update(updates)
            pr["updated_at"] = datetime.utcnow().isoformat() + "Z"
            _save_json(_prs_path(), prs)
            return PullRequest(**pr)
    return None


def delete_pull_request(pr_id: str) -> bool:
    prs = _load_json(_prs_path())
    before = len(prs)
    prs = [pr for pr in prs if pr["id"] != pr_id]
    if len(prs) == before:
        return False
    _save_json(_prs_path(), prs)
    return True


# ── Checkpoint Restore ─────────────────────────────────────────────────────


def list_restores(run_id: str | None = None) -> list[CheckpointRestore]:
    all_r = _load_json(_restores_path())
    if run_id:
        all_r = [r for r in all_r if r.get("run_id") == run_id]
    all_r.sort(key=lambda r: r.get("restored_at", ""), reverse=True)
    return [CheckpointRestore(**r) for r in all_r]


def record_restore(snapshot_id: str, run_id: str, restored_by: str = "", note: str = "") -> CheckpointRestore:
    restores = _load_json(_restores_path())
    now = datetime.utcnow().isoformat() + "Z"
    r = CheckpointRestore(
        id=f"restore-{uuid4().hex[:8]}",
        snapshot_id=snapshot_id,
        run_id=run_id,
        restored_at=now,
        restored_by=restored_by,
        note=note,
    )
    restores.append(r.model_dump())
    _save_json(_restores_path(), restores)
    return r


# ── Snapshot run artifacts ──────────────────────────────────────────────────


def snapshot_from_run(run_id: str, artifact_root: str = ".runtime/artifacts") -> Snapshot | None:
    """Create a snapshot from the current artifacts of a run."""
    run_dir = Path(artifact_root) / run_id
    if not run_dir.exists():
        return None

    files: list[SnapshotFile] = []
    file_extensions = {".tex", ".bib", ".md", ".json"}
    for fpath in run_dir.iterdir():
        if fpath.is_file() and fpath.suffix in file_extensions:
            try:
                content = fpath.read_text(encoding="utf-8")
                rel_path = fpath.name
                files.append(SnapshotFile(
                    path=rel_path,
                    content=content,
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
                ))
            except Exception:
                pass

    if not files:
        return None

    # Determine parent snapshot
    snapshots = list_snapshots(run_id=run_id)
    parent_id = snapshots[0].id if snapshots else None
    branch = snapshots[0].branch if snapshots else "main"

    return create_snapshot(
        run_id=run_id,
        branch=branch,
        message=f"Auto-snapshot of run {run_id[:12]}",
        author="system",
        files=files,
        parent_id=parent_id,
    )
