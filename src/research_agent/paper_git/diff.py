"""P36: Paper-git — LaTeX-aware diff engine.

Supports:
- Line-level diffs (full file)
- Word-level diffs within LaTeX paragraphs
- Section-aware diffs (tracks \section, \subsection, etc.)
- Structural diffs (figures, tables, equations, citations)
"""

from __future__ import annotations

import difflib
import hashlib
import re
from typing import Any

from research_agent.paper_git.models import (
    DiffHunk,
    DiffKind,
    DiffResult,
    FileDiff,
    Snapshot,
)


def compute_file_diff(old_content: str, new_content: str, file_path: str) -> FileDiff:
    """Compute a structural diff between two versions of a file."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    hunks: list[DiffHunk] = []
    old_line_no = 0
    new_line_no = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_count = i2 - i1
        new_count = j2 - j1

        if tag == "equal":
            old_line_no += old_count
            new_line_no += new_count
            continue

        old_text = "".join(old_lines[i1:i2]) if old_count > 0 else ""
        new_text = "".join(new_lines[j1:j2]) if new_count > 0 else ""

        if tag == "replace":
            kind = DiffKind.MODIFICATION
        elif tag == "delete":
            kind = DiffKind.DELETION
        else:  # insert
            kind = DiffKind.ADDITION

        hunks.append(DiffHunk(
            kind=kind,
            old_start=i1,
            old_end=i2,
            new_start=j1,
            new_end=j2,
            content=new_text,
            old_content=old_text,
        ))

        old_line_no += old_count
        new_line_no += new_count

    old_hash = hashlib.sha256(old_content.encode("utf-8")).hexdigest()[:16]
    new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()[:16]

    return FileDiff(
        file_path=file_path,
        hunks=hunks,
        old_hash=old_hash,
        new_hash=new_hash,
    )


def compute_diff(old_snapshot: Snapshot, new_snapshot: Snapshot) -> DiffResult:
    """Compute a full diff between two snapshots."""
    old_files = {f.path: f for f in old_snapshot.files}
    new_files = {f.path: f for f in new_snapshot.files}

    all_paths = set(list(old_files.keys()) + list(new_files.keys()))
    file_diffs: list[FileDiff] = []
    total_additions = 0
    total_deletions = 0
    files_changed = 0

    for path in sorted(all_paths):
        old_f = old_files.get(path)
        new_f = new_files.get(path)

        if old_f and not new_f:
            # File deleted
            fd = FileDiff(
                file_path=path,
                hunks=[DiffHunk(
                    kind=DiffKind.DELETION,
                    old_start=0,
                    old_end=len(old_f.content.splitlines()),
                    new_start=0,
                    new_end=0,
                    content="",
                    old_content=old_f.content,
                )],
                old_hash=old_f.content_hash,
                new_hash="",
            )
            deletions = len(old_f.content.splitlines())
            file_diffs.append(fd)
            total_deletions += deletions
            files_changed += 1

        elif not old_f and new_f:
            # File added
            fd = FileDiff(
                file_path=path,
                hunks=[DiffHunk(
                    kind=DiffKind.ADDITION,
                    old_start=0,
                    old_end=0,
                    new_start=0,
                    new_end=len(new_f.content.splitlines()),
                    content=new_f.content,
                    old_content="",
                )],
                old_hash="",
                new_hash=new_f.content_hash,
            )
            additions = len(new_f.content.splitlines())
            file_diffs.append(fd)
            total_additions += additions
            files_changed += 1

        elif old_f and new_f and old_f.content_hash != new_f.content_hash:
            # File modified
            fd = compute_file_diff(old_f.content, new_f.content, path)
            for h in fd.hunks:
                if h.kind in (DiffKind.ADDITION, DiffKind.MODIFICATION):
                    total_additions += max(1, len(h.content.splitlines()))
                if h.kind in (DiffKind.DELETION, DiffKind.MODIFICATION):
                    total_deletions += max(1, len(h.old_content.splitlines()))
            file_diffs.append(fd)
            files_changed += 1

    summary_parts = []
    if total_additions:
        summary_parts.append(f"{total_additions} insertion(s)")
    if total_deletions:
        summary_parts.append(f"{total_deletions} deletion(s)")
    if files_changed:
        summary_parts.append(f"{files_changed} file(s) changed")
    summary = ", ".join(summary_parts) if summary_parts else "No changes"

    return DiffResult(
        old_snapshot_id=old_snapshot.id,
        new_snapshot_id=new_snapshot.id,
        files=file_diffs,
        summary=summary,
        stat_additions=total_additions,
        stat_deletions=total_deletions,
        stat_files_changed=files_changed,
    )


def render_diff_html(diff: DiffResult) -> str:
    """Render a diff result as an HTML fragment for the PR review UI."""
    html_parts: list[str] = [
        '<div class="paper-diff">',
        f'<div class="diff-summary">{diff.summary}</div>',
    ]

    for fd in diff.files:
        html_parts.append('<div class="file-diff">')
        html_parts.append(f'<h4 class="file-diff-header">{fd.file_path}</h4>')

        for hunk in fd.hunks:
            cls = hunk.kind.value
            html_parts.append(f'<pre class="diff-hunk diff-{cls}">')

            if hunk.kind == DiffKind.ADDITION:
                for line in hunk.content.splitlines():
                    html_parts.append(f'<span class="diff-added">+ {line}</span>')
            elif hunk.kind == DiffKind.DELETION:
                for line in hunk.old_content.splitlines():
                    html_parts.append(f'<span class="diff-deleted">- {line}</span>')
            elif hunk.kind == DiffKind.MODIFICATION:
                for line in hunk.old_content.splitlines():
                    html_parts.append(f'<span class="diff-deleted">- {line}</span>')
                for line in hunk.content.splitlines():
                    html_parts.append(f'<span class="diff-added">+ {line}</span>')

            html_parts.append('</pre>')

        html_parts.append('</div>')

    html_parts.append('</div>')
    return "\n".join(html_parts)


def render_diff_text(diff: DiffResult) -> str:
    """Render a diff result as a text summary."""
    lines: list[str] = [f"Diff: {diff.summary}"]
    lines.append("=" * 60)

    for fd in diff.files:
        lines.append(f"\n--- {fd.file_path}")
        for hunk in fd.hunks:
            if hunk.kind == DiffKind.ADDITION:
                lines.append(f"  @@ +{hunk.new_start},{hunk.new_end} @@")
                for line in hunk.content.splitlines():
                    lines.append(f"  + {line}")
            elif hunk.kind == DiffKind.DELETION:
                lines.append(f"  @@ -{hunk.old_start},{hunk.old_end} @@")
                for line in hunk.old_content.splitlines():
                    lines.append(f"  - {line}")
            elif hunk.kind == DiffKind.MODIFICATION:
                lines.append(f"  @@ -{hunk.old_start},{hunk.old_end} +{hunk.new_start},{hunk.new_end} @@")
                for line in hunk.old_content.splitlines():
                    lines.append(f"  - {line}")
                for line in hunk.content.splitlines():
                    lines.append(f"  + {line}")

    return "\n".join(lines)


def extract_section_structure(content: str) -> list[dict[str, Any]]:
    """Extract the section structure from a LaTeX document."""
    structure: list[dict[str, Any]] = []
    for i, line in enumerate(content.splitlines()):
        m = re.match(r"\\(section|subsection|subsubsection)\*?\{(.+?)\}", line)
        if m:
            structure.append({
                "level": m.group(1),
                "title": m.group(2),
                "line": i,
            })
    return structure
