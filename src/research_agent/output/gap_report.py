from __future__ import annotations

from typing import Any


def format_gap_report(gaps: list[dict[str, Any]]) -> str:
    if not gaps:
        return "# Gap Analysis\n\nNo gaps identified."

    lines = ["# Gap Analysis\n"]
    for i, gap in enumerate(gaps, 1):
        lines.append(f"## {i}. {gap.get('category', 'unknown').title()} Gap")
        lines.append(f"**Confidence:** {gap.get('confidence', 0):.0%}")
        lines.append(f"\n{gap.get('description', '')}\n")
        related = gap.get("related_papers", [])
        if related:
            lines.append("**Related papers:**")
            for r in related[:5]:
                lines.append(f"- {r}")
        lines.append("")

    return "\n".join(lines)
