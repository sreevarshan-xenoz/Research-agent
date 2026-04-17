from __future__ import annotations

from research_agent.orchestration.state import GraphState


def _provider_summary(findings: dict[str, dict[str, object]]) -> str:
    if not findings:
        return "No provider findings were recorded for this section."

    parts: list[str] = []
    for provider, provider_data in findings.items():
        count = int(provider_data.get("item_count", 0))
        warnings = int(provider_data.get("warning_count", 0))
        parts.append(f"{provider}: {count} items, {warnings} warnings")
    return "; ".join(parts)


def combiner_node(state: GraphState) -> dict:
    sections: list[dict[str, str]] = []

    for task in state["tasks"]:
        task_id = str(task["task_id"])
        confidence = state["section_confidence"].get(task_id, 0.0)
        findings = state["task_findings"].get(task_id, {})

        content = (
            f"Objective: {task['objective']}\n"
            f"Evidence summary: {_provider_summary(findings)}\n"
            f"Confidence score: {confidence:.2f}."
        )

        sections.append(
            {
                "task_id": task_id,
                "heading": str(task["title"]),
                "content": content,
            }
        )

    return {
        "combined_sections": sections,
        "phase": "combined",
    }
