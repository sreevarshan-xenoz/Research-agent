from __future__ import annotations

import asyncio
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.output import export_run_artifacts
from research_agent.output.latex import validate_latex_package


async def exporter_node(state: GraphState) -> dict:
    await apublish_progress(
        agent="Exporter",
        status="running",
        detail="Writing artifacts",
        message="Exporting run outputs",
    )
    run_warnings = list(state["run_warnings"])
    validation_errors = validate_latex_package(
        template_name=state["template"],
        main_tex=state["latex_main"],
        bibtex=state["bibtex"],
    )
    if validation_errors:
        run_warnings.extend([f"export_validation:{error}" for error in validation_errors])
        await apublish_progress(
            agent="Exporter",
            status="error",
            detail="Validation failed",
            message="Export blocked by validation gate",
        )
        return {
            "phase": "validation_failed",
            "stop_reason": "validation_failed",
            "run_warnings": run_warnings,
        }

    summary = {
        "run_id": state["run_id"],
        "topic": state["topic"],
        "template": state["template"],
        "phase": state["phase"],
        "stop_reason": state["stop_reason"],
        "critic_notes": state["critic_notes"],
        "section_confidence": state["section_confidence"],
        "warning_count": len(run_warnings),
    }

    artifact_dir = await asyncio.to_thread(
        export_run_artifacts,
        artifact_root=state["artifact_root"],
        run_id=state["run_id"],
        main_tex=state["latex_main"],
        bibtex=state["bibtex"],
        summary=summary,
        template_name=state["template"],
    )

    await apublish_progress(
        agent="Exporter",
        status="complete",
        detail="Artifacts written",
        message="Export complete",
    )
    return {
        "artifact_dir": artifact_dir,
        "phase": "completed",
        "stop_reason": "completed",
        "run_warnings": run_warnings,
    }
