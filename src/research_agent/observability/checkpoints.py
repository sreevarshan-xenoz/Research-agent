from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
from typing import Any

from research_agent.orchestration.state import SubtopicTask, WorkflowState


logger = logging.getLogger(__name__)


def _checkpoint_root() -> Path:
    root = Path(os.getenv("CHECKPOINT_ROOT", ".runtime/checkpoints")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _event_root() -> Path:
    root = Path(os.getenv("RUN_EVENT_ROOT", ".runtime/events")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _serialize_state(state: WorkflowState) -> dict[str, Any]:
    return {
        "run_id": state.run_id,
        "topic": state.topic,
        "template": state.template,
        "phase": state.phase,
        "iteration_index": state.iteration_index,
        "max_iterations": state.max_iterations,
        "depth": state.depth,
        "autonomy_mode": state.autonomy_mode,
        "max_runtime_minutes": state.max_runtime_minutes,
        "max_cost_usd": state.max_cost_usd,
        "estimated_cost_usd": state.estimated_cost_usd,
        "started_at": state.started_at,
        "interrupted": bool(state.interrupted),
        "stop_reason": state.stop_reason,
        "tasks": [
            {
                "task_id": task.task_id,
                "title": task.title,
                "objective": task.objective,
                "depends_on": list(task.depends_on),
                "status": task.status,
            }
            for task in state.tasks
        ],
        "section_confidence": dict(state.section_confidence),
        "clarification_questions": list(state.clarification_questions),
        "needs_clarification": state.needs_clarification,
        "task_findings": dict(state.task_findings),
        "critic_notes": list(state.critic_notes),
        "combined_sections": list(state.combined_sections),
        "citations": list(state.citations),
        "figures": list(state.figures),
        "latex_main": state.latex_main,
        "bibtex": state.bibtex,
        "presentation_tex": state.presentation_tex,
        "poster_tex": state.poster_tex,
        "future_research_agenda": state.future_research_agenda,
        "comparison_table": state.comparison_table,
        "guard_report": state.guard_report,
        "math_verification_report": state.math_verification_report,
        "peer_review_report": state.peer_review_report,
        "peer_reviews": list(state.peer_reviews),
        "peer_review_meta": state.peer_review_meta,
        "peer_review_personas": list(state.peer_review_personas),
        "knowledge_graph": state.knowledge_graph,
        "bias_report": state.bias_report,
        "artifact_root": state.artifact_root,
        "artifact_dir": state.artifact_dir,
        "run_warnings": list(state.run_warnings),
    }


def _deserialize_state(payload: dict[str, Any]) -> WorkflowState:
    tasks = [SubtopicTask(**task) for task in payload.get("tasks", [])]
    return WorkflowState(
        run_id=payload["run_id"],
        topic=payload["topic"],
        template=payload.get("template", "ieee"),
        phase=payload.get("phase", "intake"),
        iteration_index=int(payload.get("iteration_index", 0)),
        max_iterations=int(payload.get("max_iterations", 4)),
        depth=payload.get("depth", "balanced"),
        autonomy_mode=payload.get("autonomy_mode", "hybrid"),
        max_runtime_minutes=int(payload.get("max_runtime_minutes", 25)),
        max_cost_usd=float(payload.get("max_cost_usd", 5.0)),
        estimated_cost_usd=float(payload.get("estimated_cost_usd", 0.0)),
        started_at=float(payload.get("started_at", time.time())),
        interrupted=bool(payload.get("interrupted", False)),
        stop_reason=payload.get("stop_reason"),
        tasks=tasks,
        section_confidence=dict(payload.get("section_confidence", {})),
        clarification_questions=list(payload.get("clarification_questions", [])),
        needs_clarification=bool(payload.get("needs_clarification", False)),
        task_findings=dict(payload.get("task_findings", {})),
        critic_notes=list(payload.get("critic_notes", [])),
        combined_sections=list(payload.get("combined_sections", [])),
        citations=list(payload.get("citations", [])),
        figures=list(payload.get("figures", [])),
        latex_main=payload.get("latex_main", ""),
        bibtex=payload.get("bibtex", ""),
        presentation_tex=payload.get("presentation_tex"),
        poster_tex=payload.get("poster_tex"),
        future_research_agenda=payload.get("future_research_agenda"),
        comparison_table=payload.get("comparison_table"),
        guard_report=payload.get("guard_report"),
        math_verification_report=payload.get("math_verification_report"),
        peer_review_report=payload.get("peer_review_report"),
        peer_reviews=list(payload.get("peer_reviews", [])),
        peer_review_meta=payload.get("peer_review_meta"),
        peer_review_personas=list(payload.get("peer_review_personas", [])),
        knowledge_graph=payload.get("knowledge_graph"),
        bias_report=payload.get("bias_report"),
        artifact_root=payload.get("artifact_root", ".runtime/artifacts"),
        artifact_dir=payload.get("artifact_dir", ""),
        run_warnings=list(payload.get("run_warnings", [])),
    )


def save_checkpoint(state: WorkflowState, *, label: str) -> Path:
    root = _checkpoint_root() / state.run_id
    root.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    millis = int((time.time() % 1) * 1000)
    checkpoint_path = root / f"{stamp}-{millis:03d}-{label}.json"

    payload = {
        "run_id": state.run_id,
        "saved_at": time.time(),
        "label": label,
        "state": _serialize_state(state),
    }
    checkpoint_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return checkpoint_path


def load_latest_checkpoint(run_id: str) -> WorkflowState | None:
    run_dir = _checkpoint_root() / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        return None

    checkpoints = sorted(run_dir.glob("*.json"))
    if not checkpoints:
        return None

    latest = checkpoints[-1]
    payload = json.loads(latest.read_text(encoding="utf-8"))
    state_payload = payload.get("state", {})
    if not isinstance(state_payload, dict):
        return None

    return _deserialize_state(state_payload)


def save_session_id(run_id: str) -> None:
    """Saves the current run_id to a session file for recovery."""
    session_file = _checkpoint_root() / "last_session.txt"
    session_file.write_text(run_id, encoding="utf-8")


def load_session_id() -> str | None:
    """Loads the last saved run_id."""
    session_file = _checkpoint_root() / "last_session.txt"
    if session_file.exists():
        return session_file.read_text(encoding="utf-8").strip()
    return None


def cleanup_old_checkpoints(max_age_days: int = 7) -> int:
    """Delete checkpoint files older than max_age_days.

    Scans all run_id directories under CHECKPOINT_ROOT and removes
    individual checkpoint JSON files whose saved_at timestamp is
    older than max_age_days. Empty run directories are then cleaned up.

    Returns:
        Number of checkpoint files removed.
    """
    now = time.time()
    cutoff = now - (max_age_days * 86400)
    removed = 0

    root = _checkpoint_root()
    if not root.exists():
        return 0

    for run_dir in root.iterdir():
        if not run_dir.is_dir():
            continue
        for cp_file in run_dir.glob("*.json"):
            try:
                payload = json.loads(cp_file.read_text(encoding="utf-8"))
                saved_at = float(payload.get("saved_at", 0))
                if saved_at < cutoff:
                    cp_file.unlink()
                    removed += 1
            except Exception as exc:
                # If we can't parse the file, remove it anyway (corrupted)
                logger.warning("Removing unparseable checkpoint file: %s: %s", cp_file, exc)
                try:
                    cp_file.unlink()
                    removed += 1
                except Exception as unlink_err:
                    logger.warning("Failed to remove corrupted checkpoint: %s: %s", cp_file, unlink_err)

        # Remove empty run directories
        try:
            if not any(run_dir.iterdir()):
                run_dir.rmdir()
        except Exception as exc:
            logger.debug("Could not remove empty run directory %s: %s", run_dir, exc)

    # Also clean up old event files
    event_root = _event_root()
    if event_root.exists():
        for event_file in event_root.glob("*.ndjson"):
            try:
                age = now - event_file.stat().st_mtime
                if age > cutoff:
                    event_file.unlink()
                    removed += 1
            except Exception as exc:
                logger.debug("Could not clean up event file %s: %s", event_file, exc)

    return removed


def append_run_event(*, run_id: str, event: str, payload: dict[str, Any]) -> Path:
    event_path = _event_root() / f"{run_id}.ndjson"
    envelope = {
        "ts": time.time(),
        "event": event,
        "payload": payload,
    }
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(envelope, ensure_ascii=True, default=str) + "\n")
    return event_path
