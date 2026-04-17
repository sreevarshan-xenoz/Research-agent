from __future__ import annotations

from research_agent.orchestration.state import GraphState
from research_agent.output import export_run_artifacts


def exporter_node(state: GraphState) -> dict:
    summary = {
        "run_id": state["run_id"],
        "topic": state["topic"],
        "template": state["template"],
        "phase": state["phase"],
        "stop_reason": state["stop_reason"],
        "critic_notes": state["critic_notes"],
        "section_confidence": state["section_confidence"],
        "warning_count": len(state["run_warnings"]),
    }

    artifact_dir = export_run_artifacts(
        artifact_root=state["artifact_root"],
        run_id=state["run_id"],
        main_tex=state["latex_main"],
        bibtex=state["bibtex"],
        summary=summary,
        template_name=state["template"],
    )

    return {
        "artifact_dir": artifact_dir,
        "phase": "completed",
        "stop_reason": "completed",
    }
