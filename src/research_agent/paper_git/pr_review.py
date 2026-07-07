"""P36: Paper-git — PR-style review workflow.

Supports:
- Creating/updating/closing pull requests
- Adding inline review comments on diffs
- Approving or requesting changes
- Merging approved PRs
- (Future) GitHub-style review threads
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from typing import Any

from research_agent.paper_git.diff import compute_diff, render_diff_text
from research_agent.paper_git.models import (
    PRComment,
    PRStatus,
    PullRequest,
)
from research_agent.paper_git.store import (
    get_branch,
    get_pull_request,
    get_snapshot,
    update_pull_request,
)
from research_agent.paper_git.branch import merge_branches


def add_comment(
    pr_id: str,
    author: str,
    body: str,
    file_path: str = "",
    line_start: int = 0,
    line_end: int = 0,
) -> PRComment | None:
    """Add a review comment to a pull request."""
    pr = get_pull_request(pr_id)
    if not pr:
        return None

    now = datetime.utcnow().isoformat() + "Z"
    comment = PRComment(
        id=f"c-{uuid4().hex[:8]}",
        author=author,
        body=body,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        created_at=now,
    )
    pr.comments.append(comment)
    update_pull_request(pr_id, {"comments": [c.model_dump() for c in pr.comments]})
    return comment


def resolve_comment(pr_id: str, comment_id: str) -> bool:
    """Mark a comment as resolved."""
    pr = get_pull_request(pr_id)
    if not pr:
        return False
    for c in pr.comments:
        if c.id == comment_id:
            c.resolved = True
            update_pull_request(pr_id, {
                "comments": [cc.model_dump() for cc in pr.comments]
            })
            return True
    return False


def approve_pr(pr_id: str, approver: str) -> PullRequest | None:
    """Approve a pull request."""
    pr = get_pull_request(pr_id)
    if not pr:
        return None
    if approver not in pr.approvals:
        pr.approvals.append(approver)
    pr.status = PRStatus.APPROVED
    update_pull_request(pr_id, {
        "approvals": pr.approvals,
        "status": PRStatus.APPROVED.value,
    })
    return pr


def request_changes(pr_id: str, reviewer: str, reason: str = "") -> PullRequest | None:
    """Request changes on a pull request (marks as changes requested)."""
    pr = get_pull_request(pr_id)
    if not pr:
        return None
    pr.status = PRStatus.CHANGES_REQUESTED
    now = datetime.utcnow().isoformat() + "Z"
    comment = PRComment(
        id=f"c-{uuid4().hex[:8]}",
        author=reviewer,
        body=f"Changes requested: {reason}" if reason else "Changes requested",
        created_at=now,
    )
    pr.comments.append(comment)
    update_pull_request(pr_id, {
        "status": PRStatus.CHANGES_REQUESTED.value,
        "comments": [c.model_dump() for c in pr.comments],
    })
    return pr


def merge_pr(pr_id: str, merged_by: str) -> dict[str, Any]:
    """Merge an approved pull request."""
    pr = get_pull_request(pr_id)
    if not pr:
        return {"success": False, "message": "Pull request not found"}

    if pr.status != PRStatus.APPROVED:
        return {
            "success": False,
            "message": f"PR is {pr.status.value}, not approved. Must be approved before merging.",
        }

    # Check source and target branches exist
    source_b = get_branch(pr.source_branch)
    target_b = get_branch(pr.target_branch)
    if not source_b:
        return {"success": False, "message": f"Source branch '{pr.source_branch}' not found"}
    if not target_b:
        return {"success": False, "message": f"Target branch '{pr.target_branch}' not found"}

    # Perform the merge
    result = merge_branches(
        source_branch=pr.source_branch,
        target_branch=pr.target_branch,
        author=merged_by,
        message=f"Merge PR #{pr_id}: {pr.title}",
    )

    now = datetime.utcnow().isoformat() + "Z"
    update_pull_request(pr_id, {
        "status": PRStatus.MERGED.value if result.success else pr.status.value,
        "merged_at": now,
        "merged_by": merged_by,
        "updated_at": now,
    })

    return {
        "success": result.success,
        "merged_snapshot_id": result.merged_snapshot_id,
        "conflict_count": result.conflict_count,
        "conflicts": [c.model_dump() for c in result.conflicts] if result.conflicts else [],
        "message": result.message,
    }


def close_pr(pr_id: str) -> PullRequest | None:
    """Close a pull request without merging."""
    return update_pull_request(pr_id, {"status": PRStatus.CLOSED.value})


def get_pr_diff(pr_id: str) -> dict[str, Any]:
    """Get the diff for a pull request."""
    pr = get_pull_request(pr_id)
    if not pr:
        return {"error": "Pull request not found"}

    source_snapshot = get_snapshot(pr.snapshot_id)
    base_snapshot = get_snapshot(pr.base_snapshot_id)

    if not source_snapshot or not base_snapshot:
        return {"error": "Snapshots not found for diff"}

    diff = compute_diff(base_snapshot, source_snapshot)
    return {
        "diff": diff.model_dump(),
        "diff_text": render_diff_text(diff),
        "source_branch": pr.source_branch,
        "target_branch": pr.target_branch,
    }


def get_pr_comment_threads(pr_id: str) -> list[dict[str, Any]]:
    """Get comments grouped by file for a PR review."""
    pr = get_pull_request(pr_id)
    if not pr:
        return []

    threads: dict[str, list[PRComment]] = {}
    for c in pr.comments:
        key = c.file_path or "__general__"
        if key not in threads:
            threads[key] = []
        threads[key].append(c)

    return [
        {"file_path": k if k != "__general__" else "", "comments": [cc.model_dump() for cc in v]}
        for k, v in threads.items()
    ]
