from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, TypedDict


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
    language: str
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
    critic_user_feedback: str | None
    combined_sections: list[dict[str, Any]]
    citations: list[dict[str, str]]
    figures: list[dict[str, str]]
    latex_main: str
    bibtex: str
    presentation_tex: str | None
    poster_tex: str | None
    future_research_agenda: str | None
    comparison_table: str | None
    guard_report: str | None
    math_verification_report: str | None
    peer_review_report: str | None
    knowledge_graph: dict[str, Any] | None
    bias_report: str | None
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
    language: str = "en"
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
    critic_user_feedback: Optional[str] = None
    combined_sections: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, str]] = field(default_factory=list)
    figures: List[Dict[str, str]] = field(default_factory=list)
    latex_main: str = ""
    bibtex: str = ""
    presentation_tex: Optional[str] = None
    poster_tex: Optional[str] = None
    future_research_agenda: Optional[str] = None
    comparison_table: Optional[str] = None
    guard_report: Optional[str] = None
    math_verification_report: Optional[str] = None
    peer_review_report: Optional[str] = None
    knowledge_graph: Optional[Dict[str, Any]] = None
    bias_report: Optional[str] = None
    artifact_root: str = ".runtime/artifacts"
    artifact_dir: str = ""
    run_warnings: List[str] = field(default_factory=list)


def to_graph_state(state: WorkflowState) -> GraphState:
    return {
        "run_id": state.run_id,
        "topic": state.topic,
        "template": state.template,
        "language": state.language,
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
        "critic_user_feedback": state.critic_user_feedback,
        "combined_sections": state.combined_sections,
        "citations": state.citations,
        "figures": state.figures,
        "latex_main": state.latex_main,
        "bibtex": state.bibtex,
        "presentation_tex": state.presentation_tex,
        "poster_tex": state.poster_tex,
        "future_research_agenda": state.future_research_agenda,
        "comparison_table": state.comparison_table,
        "guard_report": state.guard_report,
        "math_verification_report": state.math_verification_report,
        "peer_review_report": state.peer_review_report,
        "knowledge_graph": state.knowledge_graph,
        "bias_report": state.bias_report,
        "artifact_root": state.artifact_root,
        "artifact_dir": state.artifact_dir,
        "run_warnings": state.run_warnings,
    }


def from_graph_state(state: GraphState) -> WorkflowState:
    return WorkflowState(
        run_id=state["run_id"],
        topic=state["topic"],
        template=state["template"],
        language=state.get("language", "en"),
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
        needs_clarification=bool(state["needs_clarification"]),
        task_findings=state["task_findings"],
        critic_notes=state["critic_notes"],
        critic_user_feedback=state.get("critic_user_feedback"),
        combined_sections=state["combined_sections"],
        citations=state["citations"],
        figures=state.get("figures", []),
        latex_main=state["latex_main"],
        bibtex=state["bibtex"],
        presentation_tex=state.get("presentation_tex"),
        poster_tex=state.get("poster_tex"),
        future_research_agenda=state.get("future_research_agenda"),
        comparison_table=state.get("comparison_table"),
        guard_report=state.get("guard_report"),
        math_verification_report=state.get("math_verification_report"),
        peer_review_report=state.get("peer_review_report"),
        knowledge_graph=state.get("knowledge_graph"),
        bias_report=state.get("bias_report"),
        artifact_root=state["artifact_root"],
        artifact_dir=state["artifact_dir"],
        run_warnings=state["run_warnings"],
    )
