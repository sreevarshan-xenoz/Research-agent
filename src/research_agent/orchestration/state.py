from __future__ import annotations

from dataclasses import dataclass, field
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
    stop_reason: str | None
    tasks: list[GraphTask]
    section_confidence: dict[str, float]
    clarification_questions: list[str]
    needs_clarification: bool
    task_findings: dict[str, dict[str, dict[str, object]]]


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
    stop_reason: Optional[str] = None
    tasks: List[SubtopicTask] = field(default_factory=list)
    section_confidence: Dict[str, float] = field(default_factory=dict)
    clarification_questions: List[str] = field(default_factory=list)
    needs_clarification: bool = False
    task_findings: Dict[str, Dict[str, Dict[str, object]]] = field(default_factory=dict)


def to_graph_state(state: WorkflowState) -> GraphState:
    return {
        "run_id": state.run_id,
        "topic": state.topic,
        "template": state.template,
        "phase": state.phase,
        "iteration_index": state.iteration_index,
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
    }


def from_graph_state(state: GraphState) -> WorkflowState:
    return WorkflowState(
        run_id=state["run_id"],
        topic=state["topic"],
        template=state["template"],
        phase=state["phase"],
        iteration_index=state["iteration_index"],
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
    )
