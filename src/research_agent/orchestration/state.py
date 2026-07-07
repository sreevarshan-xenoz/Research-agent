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
    gap_analysis: list[dict[str, Any]] | None
    comparison_table: str | None
    guard_report: str | None
    math_verification_report: str | None
    peer_review_report: str | None
    # P22: Multi-modal analysis results
    multi_modal_results: list[dict[str, Any]]
    # P37: Multi-persona peer review with confidence scoring
    peer_reviews: list[dict[str, Any]]  # Individual persona reviews as dicts
    peer_review_meta: dict[str, Any] | None  # Aggregated meta-review
    peer_review_personas: list[str]  # Personas used
    knowledge_graph: dict[str, Any] | None
    citation_graph_data: dict[str, Any] | None
    bias_report: str | None
    artifact_root: str
    artifact_dir: str
    acm_layout: str | None
    run_warnings: list[str]
    # Deep Research fields (P21)
    search_rounds: dict[str, list[dict[str, Any]]]
    termination_signals: dict[str, str]
    chained_papers: list[dict[str, Any]]
    chained_paper_ids: list[str]
    # Code Sandbox fields (P24)
    empirical_claims: list[dict[str, Any]]
    code_verification_items: list[dict[str, Any]]
    code_reproducibility_report: str | None
    # P26: Advanced AI Research Assistant fields
    generated_hypotheses: list[dict[str, Any]]
    research_strategy: dict[str, Any] | None
    gap_exploration: dict[str, Any] | None
    # User's past research topics (sourced from session history + agent memory)
    past_research_topics: list[str]


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
    max_iterations: int = 4
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
    gap_analysis: Optional[List[Dict[str, Any]]] = None
    comparison_table: Optional[str] = None
    guard_report: Optional[str] = None
    math_verification_report: Optional[str] = None
    peer_review_report: Optional[str] = None
    # P22: Multi-modal analysis results
    multi_modal_results: List[Dict[str, Any]] = field(default_factory=list)
    # P37: Multi-persona peer review with confidence scoring
    peer_reviews: List[Dict[str, Any]] = field(default_factory=list)
    peer_review_meta: Optional[Dict[str, Any]] = None
    peer_review_personas: List[str] = field(default_factory=list)
    knowledge_graph: Optional[Dict[str, Any]] = None
    citation_graph_data: Optional[Dict[str, Any]] = None
    bias_report: Optional[str] = None
    acm_layout: Optional[str] = None
    artifact_root: str = ".runtime/artifacts"
    artifact_dir: str = ""
    run_warnings: List[str] = field(default_factory=list)
    # Deep Research fields (P21)
    search_rounds: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    termination_signals: Dict[str, str] = field(default_factory=dict)
    chained_papers: List[Dict[str, Any]] = field(default_factory=list)
    chained_paper_ids: List[str] = field(default_factory=list)
    # Code Sandbox fields (P24)
    empirical_claims: List[Dict[str, Any]] = field(default_factory=list)
    code_verification_items: List[Dict[str, Any]] = field(default_factory=list)
    code_reproducibility_report: Optional[str] = None
    # P26: Advanced AI Research Assistant fields
    generated_hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    research_strategy: Optional[Dict[str, Any]] = None
    gap_exploration: Optional[Dict[str, Any]] = None
    # User-specific past research topics (sourced from session history + agent memory)
    past_research_topics: List[str] = field(default_factory=list)


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
        "gap_analysis": state.gap_analysis,
        "comparison_table": state.comparison_table,
        "guard_report": state.guard_report,
        "math_verification_report": state.math_verification_report,
        "peer_review_report": state.peer_review_report,
        "peer_reviews": state.peer_reviews,
        "peer_review_meta": state.peer_review_meta,
        "peer_review_personas": state.peer_review_personas,
        "knowledge_graph": state.knowledge_graph,
        "citation_graph_data": state.citation_graph_data,
        "bias_report": state.bias_report,
        "artifact_root": state.artifact_root,
        "artifact_dir": state.artifact_dir,
        "acm_layout": state.acm_layout,
        "run_warnings": state.run_warnings,
        "search_rounds": state.search_rounds,
        "termination_signals": state.termination_signals,
        "chained_papers": state.chained_papers,
        "chained_paper_ids": state.chained_paper_ids,
        "empirical_claims": state.empirical_claims,
        "code_verification_items": state.code_verification_items,
        "code_reproducibility_report": state.code_reproducibility_report,
        "multi_modal_results": state.multi_modal_results,
        "generated_hypotheses": state.generated_hypotheses,
        "research_strategy": state.research_strategy,
        "gap_exploration": state.gap_exploration,
        "past_research_topics": state.past_research_topics,
    }


def from_graph_state(state: GraphState) -> WorkflowState:
    return WorkflowState(
        run_id=state["run_id"],
        topic=state["topic"],
        template=state["template"],
        language=state.get("language", "en"),
        phase=state["phase"],
        iteration_index=state["iteration_index"],
        max_iterations=state.get("max_iterations", 4),
        depth=state.get("depth", "balanced"),
        autonomy_mode=state.get("autonomy_mode", "hybrid"),
        max_runtime_minutes=state.get("max_runtime_minutes", 25),
        max_cost_usd=state.get("max_cost_usd", 5.0),
        estimated_cost_usd=state.get("estimated_cost_usd", 0.0),
        started_at=state.get("started_at", time.time()),
        interrupted=state.get("interrupted", False),
        stop_reason=state.get("stop_reason"),
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
        gap_analysis=state.get("gap_analysis"),
        comparison_table=state.get("comparison_table"),
        guard_report=state.get("guard_report"),
        math_verification_report=state.get("math_verification_report"),
        peer_review_report=state.get("peer_review_report"),
        peer_reviews=list(state.get("peer_reviews", [])),
        peer_review_meta=state.get("peer_review_meta"),
        peer_review_personas=list(state.get("peer_review_personas", [])),
        knowledge_graph=state.get("knowledge_graph"),
        citation_graph_data=state.get("citation_graph_data"),
        bias_report=state.get("bias_report"),
        acm_layout=state.get("acm_layout"),
        artifact_root=state["artifact_root"],
        artifact_dir=state["artifact_dir"],
        run_warnings=state["run_warnings"],
        search_rounds=state.get("search_rounds", {}),
        termination_signals=state.get("termination_signals", {}),
        chained_papers=state.get("chained_papers", []),
        chained_paper_ids=state.get("chained_paper_ids", []),
        empirical_claims=state.get("empirical_claims", []),
        code_verification_items=state.get("code_verification_items", []),
        code_reproducibility_report=state.get("code_reproducibility_report"),
        multi_modal_results=state.get("multi_modal_results", []),
        generated_hypotheses=list(state.get("generated_hypotheses", [])),
        research_strategy=state.get("research_strategy"),
        gap_exploration=state.get("gap_exploration"),
        past_research_topics=list(state.get("past_research_topics", [])),
    )
