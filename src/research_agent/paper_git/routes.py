"""P36 — Paper-git: Version Control for Research API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from research_agent.app.auth import current_active_user, User
from research_agent.paper_git.branch import (
    merge_branches,
    resolve_conflict,
)
from research_agent.paper_git.diff import compute_diff, render_diff_text
from research_agent.paper_git.models import (
    Branch,
    DiffResult,
    MergeResult,
    PRStatus,
    PullRequest,
    Snapshot,
    SnapshotFile,
    CheckpointRestore,
)
from research_agent.paper_git.pr_review import (
    add_comment,
    approve_pr,
    close_pr,
    get_pr_comment_threads,
    get_pr_diff,
    merge_pr,
    request_changes,
    resolve_comment,
)
from research_agent.paper_git.store import (
    get_branch,
    create_branch,
    create_pull_request,
    create_snapshot,
    delete_branch,
    delete_snapshot,
    get_pull_request,
    get_snapshot,
    list_branches,
    list_pull_requests,
    list_restores,
    list_snapshots,
    record_restore,
    snapshot_from_run,
)

router = APIRouter(prefix="/api/paper-git", tags=["Paper-git"])


# ── Snapshots ──────────────────────────────────────────────────────────────


@router.get("/snapshots")
async def list_run_snapshots(
    run_id: str = "",
    branch: str = "",
    user: User = Depends(current_active_user),
) -> list[Snapshot]:
    return list_snapshots(run_id=run_id or None, branch=branch or None)


@router.post("/snapshots/auto/{run_id}")
async def auto_snapshot(
    run_id: str,
    user: User = Depends(current_active_user),
) -> Snapshot:
    """Auto-snapshot: capture current run artifacts as a new snapshot."""
    snap = snapshot_from_run(run_id)
    if not snap:
        raise HTTPException(status_code=400, detail=f"No artifacts found for run {run_id}")
    return snap


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot_by_id(
    snapshot_id: str,
    user: User = Depends(current_active_user),
) -> Snapshot:
    snap = get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap


@router.post("/snapshots")
async def take_snapshot(
    run_id: str,
    branch: str = "main",
    message: str = "",
    author: str = "",
    file_paths: list[str] | None = None,
    user: User = Depends(current_active_user),
) -> Snapshot:
    """Take a manual snapshot of a run's artifacts."""
    # Get the artifacts from the run directory
    from pathlib import Path

    artifact_root = ".runtime/artifacts"
    run_dir = Path(artifact_root) / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run directory not found: {run_id}")

    files: list[SnapshotFile] = []
    exts = {".tex", ".bib", ".md", ".json"}
    for fpath in run_dir.iterdir():
        if fpath.is_file() and fpath.suffix in exts:
            if file_paths and fpath.name not in file_paths:
                continue
            try:
                content = fpath.read_text(encoding="utf-8")
                files.append(SnapshotFile(path=fpath.name, content=content))
            except Exception:
                pass

    if not files:
        raise HTTPException(status_code=400, detail="No snapshot-compatible files found (.tex, .bib, .md, .json)")

    # Find parent snapshot
    existing = list_snapshots(run_id=run_id, branch=branch)
    parent_id = existing[0].id if existing else None

    return create_snapshot(
        run_id=run_id,
        branch=branch,
        message=message or f"Manual snapshot from run {run_id[:12]}",
        author=author or str(user.id),
        files=files,
        parent_id=parent_id,
    )


@router.delete("/snapshots/{snapshot_id}")
async def remove_snapshot(
    snapshot_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, bool]:
    if not delete_snapshot(snapshot_id):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"deleted": True}


# ── Diff ────────────────────────────────────────────────────────────────────


@router.get("/diff/{old_snapshot_id}/{new_snapshot_id}")
async def get_diff(
    old_snapshot_id: str,
    new_snapshot_id: str,
    user: User = Depends(current_active_user),
) -> DiffResult:
    old_snap = get_snapshot(old_snapshot_id)
    new_snap = get_snapshot(new_snapshot_id)
    if not old_snap:
        raise HTTPException(status_code=404, detail=f"Snapshot {old_snapshot_id} not found")
    if not new_snap:
        raise HTTPException(status_code=404, detail=f"Snapshot {new_snapshot_id} not found")
    return compute_diff(old_snap, new_snap)


@router.get("/diff/{old_snapshot_id}/{new_snapshot_id}/text")
async def get_diff_text(
    old_snapshot_id: str,
    new_snapshot_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, str]:
    old_snap = get_snapshot(old_snapshot_id)
    new_snap = get_snapshot(new_snapshot_id)
    if not old_snap or not new_snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    diff = compute_diff(old_snap, new_snap)
    return {"text": render_diff_text(diff)}


# ── Branches ───────────────────────────────────────────────────────────────


@router.get("/branches")
async def list_all_branches(
    user: User = Depends(current_active_user),
) -> list[Branch]:
    return list_branches()


@router.get("/branches/{name}")
async def get_branch_by_name(
    name: str,
    user: User = Depends(current_active_user),
) -> Branch:
    b = get_branch(name)
    if not b:
        raise HTTPException(status_code=404, detail=f"Branch '{name}' not found")
    return b


@router.post("/branches")
async def create_new_branch(
    name: str,
    from_snapshot_id: str,
    description: str = "",
    user: User = Depends(current_active_user),
) -> Branch:
    try:
        return create_branch(
            name=name,
            from_snapshot_id=from_snapshot_id,
            description=description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/branches/{name}")
async def remove_branch(
    name: str,
    user: User = Depends(current_active_user),
) -> dict[str, bool]:
    if not delete_branch(name):
        raise HTTPException(status_code=404, detail=f"Branch '{name}' not found")
    return {"deleted": True}


# ── Merge ──────────────────────────────────────────────────────────────────


@router.post("/merge")
async def merge_branches_endpoint(
    source_branch: str,
    target_branch: str,
    author: str = "system",
    message: str = "",
    user: User = Depends(current_active_user),
) -> MergeResult:
    return merge_branches(
        source_branch=source_branch,
        target_branch=target_branch,
        author=author,
        message=message,
    )


@router.post("/merge/resolve")
async def resolve_merge_conflict(
    snapshot_id: str,
    file_path: str,
    hunk_index: int,
    resolution: str,
    user: User = Depends(current_active_user),
) -> MergeResult:
    result = resolve_conflict(snapshot_id, file_path, hunk_index, resolution)
    if not result:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return result


# ── Pull Requests ──────────────────────────────────────────────────────────


@router.get("/prs")
async def list_prs(
    status: str = "",
    user: User = Depends(current_active_user),
) -> list[PullRequest]:
    s = PRStatus(status) if status else None
    return list_pull_requests(status=s)


@router.get("/prs/{pr_id}")
async def get_pr(
    pr_id: str,
    user: User = Depends(current_active_user),
) -> PullRequest:
    pr = get_pull_request(pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    return pr


@router.post("/prs")
async def create_pr(
    title: str,
    source_branch: str,
    target_branch: str = "main",
    description: str = "",
    user: User = Depends(current_active_user),
) -> PullRequest:
    try:
        pr = create_pull_request(
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            author=str(user.id),
            description=description,
        )
        return pr
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/prs/{pr_id}/comment")
async def add_pr_comment(
    pr_id: str,
    body: str,
    file_path: str = "",
    line_start: int = 0,
    line_end: int = 0,
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    comment = add_comment(
        pr_id=pr_id,
        author=str(user.id),
        body=body,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Pull request not found")
    return {"comment": comment.model_dump()}


@router.post("/prs/{pr_id}/comment/{comment_id}/resolve")
async def resolve_pr_comment(
    pr_id: str,
    comment_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, bool]:
    if not resolve_comment(pr_id, comment_id):
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"resolved": True}


@router.post("/prs/{pr_id}/approve")
async def approve_pr_endpoint(
    pr_id: str,
    user: User = Depends(current_active_user),
) -> PullRequest:
    pr = approve_pr(pr_id, str(user.id))
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    return pr


@router.post("/prs/{pr_id}/request-changes")
async def request_changes_endpoint(
    pr_id: str,
    reason: str = "",
    user: User = Depends(current_active_user),
) -> PullRequest:
    pr = request_changes(pr_id, str(user.id), reason=reason)
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    return pr


@router.post("/prs/{pr_id}/merge")
async def merge_pr_endpoint(
    pr_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    return merge_pr(pr_id, str(user.id))


@router.post("/prs/{pr_id}/close")
async def close_pr_endpoint(
    pr_id: str,
    user: User = Depends(current_active_user),
) -> PullRequest:
    pr = close_pr(pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    return pr


@router.get("/prs/{pr_id}/diff")
async def get_pr_diff_endpoint(
    pr_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    result = get_pr_diff(pr_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/prs/{pr_id}/comments")
async def get_pr_comment_threads_endpoint(
    pr_id: str,
    user: User = Depends(current_active_user),
) -> list[dict[str, Any]]:
    return get_pr_comment_threads(pr_id)


# ── Checkpoint Restore ─────────────────────────────────────────────────────


@router.get("/restores")
async def list_run_restores(
    run_id: str = "",
    user: User = Depends(current_active_user),
) -> list[CheckpointRestore]:
    return list_restores(run_id=run_id or None)


@router.post("/restores")
async def restore_from_snapshot(
    snapshot_id: str,
    run_id: str,
    note: str = "",
    user: User = Depends(current_active_user),
) -> CheckpointRestore:
    snap = get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Restore files to the run's artifact directory
    from pathlib import Path

    artifact_root = ".runtime/artifacts"
    run_dir = Path(artifact_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    restored_count = 0
    for f in snap.files:
        try:
            (run_dir / f.path).write_text(f.content, encoding="utf-8")
            restored_count += 1
        except Exception:
            pass

    restore_record = record_restore(
        snapshot_id=snapshot_id,
        run_id=run_id,
        restored_by=str(user.id),
        note=f"{note} (restored {restored_count} files)" if note else f"Restored {restored_count} files",
    )

    return restore_record


# ── Stats ──────────────────────────────────────────────────────────────────


@router.get("/stats/summary")
async def paper_git_stats(
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    branches = list_branches()
    all_snapshots = list_snapshots()
    all_prs = list_pull_requests()
    restores = list_restores()

    open_prs = [pr for pr in all_prs if pr.status == PRStatus.OPEN]
    merged_prs = [pr for pr in all_prs if pr.status == PRStatus.MERGED]

    return {
        "total_snapshots": len(all_snapshots),
        "total_branches": len(branches),
        "total_pull_requests": len(all_prs),
        "open_prs": len(open_prs),
        "merged_prs": len(merged_prs),
        "total_restores": len(restores),
        "branches": [b.name for b in branches],
        "open_pr_titles": [pr.title for pr in open_prs],
    }
