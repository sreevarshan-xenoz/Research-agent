from __future__ import annotations

from research_agent.orchestration.state import GraphState


def critic_node(state: GraphState) -> dict:
    section_confidence: dict[str, float] = {}
    notes: list[str] = []

    for task in state["tasks"]:
        task_id = str(task["task_id"])
        findings = state["task_findings"].get(task_id, {})

        item_count = sum(int(provider_data.get("item_count", 0)) for provider_data in findings.values())
        warning_count = sum(
            int(provider_data.get("warning_count", 0)) for provider_data in findings.values()
        )

        if item_count == 0:
            confidence = 0.1
        else:
            confidence = max(0.0, min(1.0, (item_count / 8.0) - (warning_count * 0.04)))

        section_confidence[task_id] = round(confidence, 3)
        if confidence < 0.35:
            notes.append(f"Low evidence confidence for {task_id}")

    if not notes:
        notes.append("Evidence confidence is acceptable for initial v1 synthesis")

    return {
        "section_confidence": section_confidence,
        "critic_notes": notes,
        "phase": "critic_scored",
    }
