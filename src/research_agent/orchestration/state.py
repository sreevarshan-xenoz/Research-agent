from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional, TypedDict


class GraphTask(TypedDict):
    task_id: str
    title: str
    objective: str
    depends_on: list[str]
    status: str


class GraphState(TypedDict):
    run_id: str
    topic: str
    template: str
    phase: str
    iteration_index: int
    max_iterations: int
    depth: str
    autonomy_mode: str
    max_runtime_minutes: int
    max_cost_usd: float
    estimated_cost_usd: float
    started_at: float
    interrupted: bool
    stop_reason: str | None
    tasks: list[GraphTask]
    section_confidence: dict[str, float]
    clarification_questions: list[str]
    needs_clarification: bool
    task_findings: dict[str, dict[str, dict[str, object]]]
    critic_notes: list[str]
    combined_sections: list[dict[str, str]]
    citations: list[dict[str, str]]
    figures: list[dict[str, str]]
    latex_main: str
    bibtex: str
    artifact_root: str
    artifact_dir: str
    run_warnings: list[str]


@dataclass
class SubtopicTask:
    task_id: str
    title: str
    objective: str
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"


@dataclass
class WorkflowState:
    run_id: str
    topic: str
    template: str = "ieee"
    phase: str = "intake"
    iteration_index: int = 0
    max_iterations: int = 3
    depth: str = "balanced"
    autonomy_mode: str = "hybrid"
    max_runtime_minutes: int = 25
    max_cost_usd: float = 5.0
    estimated_cost_usd: float = 0.0
    started_at: float = field(default_factory=time.time)
    interrupted: bool = False
    stop_reason: Optional[str] = None
    tasks: List[SubtopicTask] = field(default_factory=list)
    section_confidence: Dict[str, float] = field(default_factory=dict)
    clarification_questions: List[str] = field(default_factory=list)
    needs_clarification: bool = False
    task_findings: Dict[str, Dict[str, Dict[str, object]]] = field(default_factory=dict)
    critic_notes: List[str] = field(default_factory=list)
    combined_sections: List[Dict[str, str]] = field(default_factory=list)
    citations: List[Dict[str, str]] = field(default_factory=list)
    figures: List[Dict[str, str]] = field(default_factory=list)
    latex_main: str = ""
    bibtex: str = ""
    artifact_root: str = ".runtime/artifacts"
    artifact_dir: str = ""
    run_warnings: List[str] = field(default_factory=list)


def to_graph_state(state: WorkflowState) -> GraphState:
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
        "interrupted": state.interrupted,
        "stop_reason": state.stop_reason,
        "tasks": [
            {
                "task_id": task.task_id,
                "title": task.title,
                "objective": task.objective,
                "depends_on": task.depends_on,
                "status": task.status,
            }
            for task in state.tasks
        ],
        "section_confidence": state.section_confidence,
        "clarification_questions": state.clarification_questions,
        "needs_clarification": state.needs_clarification,
        "task_findings": state.task_findings,
        "critic_notes": state.critic_notes,
        "combined_sections": state.combined_sections,
        "citations": state.citations,
        "figures": state.figures,
        "latex_main": state.latex_main,
        "bibtex": state.bibtex,
        "artifact_root": state.artifact_root,
        "artifact_dir": state.artifact_dir,
        "run_warnings": state.run_warnings,
    }


def from_graph_state(state: GraphState) -> WorkflowState:
    return WorkflowState(
        run_id=state["run_id"],
        topic=state["topic"],
        template=state["template"],
        phase=state["phase"],
        iteration_index=state["iteration_index"],
        max_iterations=state.get("max_iterations", 3),
        depth=state.get("depth", "balanced"),
        autonomy_mode=state.get("autonomy_mode", "hybrid"),
        max_runtime_minutes=state.get("max_runtime_minutes", 25),
        max_cost_usd=state.get("max_cost_usd", 5.0),
        estimated_cost_usd=state.get("estimated_cost_usd", 0.0),
        started_at=state.get("started_at", time.time()),
        interrupted=state.get("interrupted", False),
        stop_reason=state["stop_reason"],
        tasks=[
            SubtopicTask(
                task_id=task["task_id"],
                title=task["title"],
                objective=task["objective"],
                depends_on=task["depends_on"],
                status=task["status"],
            )
            for task in state["tasks"]
        ],
        section_confidence=state["section_confidence"],
        clarification_questions=state["clarification_questions"],
        needs_clarification=state["needs_clarification"],
        task_findings=state["task_findings"],
        critic_notes=state["critic_notes"],
        combined_sections=state["combined_sections"],
        citations=state["citations"],
        figures=state.get("figures", []),
        latex_main=state["latex_main"],
        bibtex=state["bibtex"],
        artifact_root=state["artifact_root"],
        artifact_dir=state["artifact_dir"],
        run_warnings=state["run_warnings"],
    )
