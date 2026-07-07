"""P36: Paper-git — Branch/merge logic with 3-way merge and conflict markers."""

from __future__ import annotations

import difflib

from research_agent.paper_git.models import (
    MergeConflict,
    MergeResult,
    Snapshot,
    SnapshotFile,
)
from research_agent.paper_git.store import (
    create_snapshot,
    get_branch,
    get_snapshot,
)


def _three_way_merge_content(
    base_content: str,
    ours_content: str,
    theirs_content: str,
    file_path: str,
) -> tuple[str, list[MergeConflict]]:
    """Perform a 3-way merge on a single file's content.

    Returns (merged_text, conflicts).
    Uses Python's difflib to compute diffs from base→ours and base→theirs,
    then attempts to merge them. Conflicts are marked with LaTeX-compatible
    conflict markers.
    """
    base_lines = base_content.splitlines(keepends=True)
    ours_lines = ours_content.splitlines(keepends=True)
    theirs_lines = theirs_content.splitlines(keepends=True)

    # Compute diffs
    ours_matcher = difflib.SequenceMatcher(None, base_lines, ours_lines)
    theirs_matcher = difflib.SequenceMatcher(None, base_lines, theirs_lines)

    ours_opcodes = ours_matcher.get_opcodes()
    theirs_opcodes = theirs_matcher.get_opcodes()

    # Merge opcodes
    merged_lines: list[str] = []
    conflicts: list[MergeConflict] = []
    hunk_index = 0

    # Simplified 3-way merge: apply changes, detect overlapping regions as conflicts
    for tag, i1, i2, j1, j2 in ours_opcodes:
        if tag == "equal":
            for line in base_lines[i1:i2]:
                if line not in merged_lines:
                    merged_lines.append(line)

    # Build a map of base line → which opcodes affect it
    # For each theirs opcode that modifies a region ours also modifies → conflict
    for tag, i1, i2, j1, j2 in theirs_opcodes:
        if tag == "equal":
            continue

        # Check if this region is also modified by ours
        for o_tag, o_i1, o_i2, o_j1, o_j2 in ours_opcodes:
            if o_tag == "equal":
                continue
            # Check overlap
            if i1 < o_i2 and o_i1 < i2:
                # Overlapping changes → conflict
                base_section = "".join(base_lines[i1:i2]) if i1 < i2 else ""
                ours_section = "".join(ours_lines[o_j1:o_j2]) if o_j1 < o_j2 else ""
                theirs_section = "".join(theirs_lines[j1:j2]) if j1 < j2 else ""

                conflict_text = (
                    f"% <<<<<<< ours\n"
                    f"{ours_section}"
                    f"% =======\n"
                    f"{theirs_section}"
                    f"% >>>>>>> theirs\n"
                )
                if conflict_text not in merged_lines:
                    merged_lines.append(conflict_text)

                conflicts.append(MergeConflict(
                    file_path=file_path,
                    hunk_index=hunk_index,
                    base_content=base_section,
                    ours_content=ours_section,
                    theirs_content=theirs_section,
                ))
                hunk_index += 1

    # Apply non-conflicting theirs changes
    for tag, i1, i2, j1, j2 in theirs_opcodes:
        if tag == "equal":
            continue
        # Check if conflicting
        is_conflict = False
        for c in conflicts:
            if c.file_path == file_path:
                base_conflict = "".join(base_lines[i1:i2]) if i1 < i2 else ""
                if base_conflict == c.base_content:
                    is_conflict = True
                    break

        if not is_conflict:
            their_lines = theirs_lines[j1:j2] if j1 < j2 else []
            for line in their_lines:
                if line not in merged_lines:
                    merged_lines.append(line)

    # Fallback: if merge produced nothing, use ours
    merged_text = "".join(merged_lines) if merged_lines else ours_content

    return merged_text, conflicts


def merge_branches(
    source_branch: str,
    target_branch: str,
    author: str = "system",
    message: str = "",
) -> MergeResult:
    """Merge source_branch into target_branch.

    Returns a MergeResult with any conflicts found.
    """
    source_b = get_branch(source_branch)
    target_b = get_branch(target_branch)

    if not source_b:
        return MergeResult(success=False, message=f"Source branch '{source_branch}' not found")
    if not target_b:
        return MergeResult(success=False, message=f"Target branch '{target_branch}' not found")

    source_snapshot = get_snapshot(source_b.head_snapshot_id)
    target_snapshot = get_snapshot(target_b.head_snapshot_id)

    if not source_snapshot:
        return MergeResult(success=False, message=f"No snapshot found for branch '{source_branch}'")
    if not target_snapshot:
        return MergeResult(success=False, message=f"No snapshot found for branch '{target_branch}'")

    # Find the merge base (common ancestor snapshot)
    base_snapshot = _find_merge_base(source_snapshot, target_snapshot)

    source_files = {f.path: f for f in source_snapshot.files}
    target_files = {f.path: f for f in target_snapshot.files}
    base_files = {f.path: f for f in (base_snapshot.files if base_snapshot else [])}

    all_paths = set(list(base_files.keys()) + list(source_files.keys()) + list(target_files.keys()))
    merged_files: list[SnapshotFile] = []
    all_conflicts: list[MergeConflict] = []

    for path in sorted(all_paths):
        base_f = base_files.get(path)
        source_f = source_files.get(path)
        target_f = target_files.get(path)

        base_content = base_f.content if base_f else ""
        source_content = source_f.content if source_f else ""
        target_content = target_f.content if target_f else ""

        if not source_f and not target_f:
            # Both deleted — skip
            continue
        if not source_f:
            # Only target has it
            if target_f:
                merged_files.append(target_f)
            continue
        if not target_f:
            # Only source has it
            if source_f:
                merged_files.append(source_f)
            continue

        # Both have the file — 3-way merge if different
        if not base_f:
            # New file in both — use source version if same hash, else conflict
            if source_f.content_hash == target_f.content_hash:
                merged_files.append(source_f)
            else:
                merged_text, conflicts = _three_way_merge_content("", source_content, target_content, path)
                merged_files.append(SnapshotFile(path=path, content=merged_text))
                all_conflicts.extend(conflicts)
        elif source_f.content_hash == target_f.content_hash:
            # Both made the same changes, or neither changed
            merged_files.append(source_f)
        elif source_f.content_hash == base_f.content_hash:
            # Only target changed
            merged_files.append(target_f)
        elif target_f.content_hash == base_f.content_hash:
            # Only source changed
            merged_files.append(source_f)
        else:
            # Both changed — 3-way merge
            merged_text, conflicts = _three_way_merge_content(base_content, source_content, target_content, path)
            merged_files.append(SnapshotFile(path=path, content=merged_text))
            all_conflicts.extend(conflicts)

    # Determine run_id from either snapshot
    run_id = source_snapshot.run_id or target_snapshot.run_id

    if all_conflicts:
        merged_snapshot = create_snapshot(
            run_id=run_id,
            branch=target_branch,
            message=f"Merge branch '{source_branch}' into '{target_branch}' (with conflicts)",
            author=author,
            files=merged_files,
            tags=["merge", "conflict"],
            metadata={"merge_source": source_branch, "merge_target": target_branch},
        )
        return MergeResult(
            success=False,
            conflict_count=len(all_conflicts),
            conflicts=all_conflicts,
            merged_snapshot_id=merged_snapshot.id,
            message=f"Merge created {len(all_conflicts)} conflict(s). Resolve them and commit.",
        )

    # Clean merge
    merged_snapshot = create_snapshot(
        run_id=run_id,
        branch=target_branch,
        message=message or f"Merge branch '{source_branch}' into '{target_branch}'",
        author=author,
        files=merged_files,
        tags=["merge"],
        metadata={"merge_source": source_branch, "merge_target": target_branch},
    )

    return MergeResult(
        success=True,
        merged_snapshot_id=merged_snapshot.id,
        message=f"Successfully merged '{source_branch}' into '{target_branch}'",
    )


def _find_merge_base(snap_a: Snapshot, snap_b: Snapshot) -> Snapshot | None:
    """Find the common ancestor snapshot between two snapshots."""
    # Collect ancestry chain for A
    a_ancestors: set[str] = set()
    current = snap_a
    while current.parent_id:
        a_ancestors.add(current.parent_id)
        parent = get_snapshot(current.parent_id)
        if not parent:
            break
        current = parent

    # Walk B's ancestry to find a common ancestor
    current = snap_b
    while current.parent_id:
        if current.parent_id in a_ancestors:
            return get_snapshot(current.parent_id)
        parent = get_snapshot(current.parent_id)
        if not parent:
            break
        current = parent

    return None


def resolve_conflict(
    snapshot_id: str,
    file_path: str,
    hunk_index: int,
    resolution: str,
) -> MergeResult | None:
    """Resolve a specific merge conflict and create a new snapshot."""
    snapshot = get_snapshot(snapshot_id)
    if not snapshot:
        return None

    # Update the file content to replace conflict markers with resolution
    updated_files: list[SnapshotFile] = []
    for f in snapshot.files:
        if f.path == file_path:
            # Replace conflict markers with resolved content
            marker_pattern = r"% <<<<<<< ours\n.*?% >>>>>>> theirs\n"
            import re
            resolved_content = re.sub(
                marker_pattern,
                resolution + "\n",
                f.content,
                count=1,
                flags=re.DOTALL,
            )
            updated_files.append(SnapshotFile(path=file_path, content=resolved_content))
        else:
            updated_files.append(f)

    merged_snapshot = create_snapshot(
        run_id=snapshot.run_id,
        branch=snapshot.branch,
        message=f"Resolved conflict in {file_path}",
        author="system",
        files=updated_files,
        tags=["merge", "resolved"],
        parent_id=snapshot_id,
    )

    # Check if all conflicts are resolved
    remaining_conflicts = 0
    for f in updated_files:
        if "% <<<<<<< ours" in f.content:
            remaining_conflicts += f.content.count("% <<<<<<< ours")

    if remaining_conflicts == 0:
        return MergeResult(
            success=True,
            merged_snapshot_id=merged_snapshot.id,
            message="All conflicts resolved and merged",
        )

    return MergeResult(
        success=False,
        conflict_count=remaining_conflicts,
        merged_snapshot_id=merged_snapshot.id,
        message=f"{remaining_conflicts} conflict(s) remaining",
    )
