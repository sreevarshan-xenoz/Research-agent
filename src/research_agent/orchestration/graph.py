from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from research_agent.orchestration.nodes import (
    awaiting_user_node,
    clarifier_node,
    dependency_blocked_node,
    get_pending_task_ids,
    get_ready_task_ids,
    intake_node,
    make_worker_node,
    planner_node,
    workers_complete_node,
)
from research_agent.orchestration.state import GraphState, WorkflowState, from_graph_state, to_graph_state
from research_agent.tools.base import BaseToolAdapter


def _route_after_clarifier(state: GraphState) -> str:
    if state["needs_clarification"] and state["clarification_questions"]:
        return "await_user"
    return "planner"


def _route_after_worker(state: GraphState) -> str:
    tasks = state["tasks"]
    pending = get_pending_task_ids(tasks)
    ready = get_ready_task_ids(tasks)

    if not pending:
        return "complete"
    if ready:
        return "loop"
    return "blocked"


def build_graph(registry: dict[str, BaseToolAdapter] | None = None):
    tool_registry = {} if registry is None else registry
    graph = StateGraph(GraphState)
    graph.add_node("intake", intake_node)
    graph.add_node("clarifier", clarifier_node)
    graph.add_node("await_user", awaiting_user_node)
    graph.add_node("planner", planner_node)
    graph.add_node("worker_executor", make_worker_node(tool_registry))
    graph.add_node("workers_complete", workers_complete_node)
    graph.add_node("workers_blocked", dependency_blocked_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "clarifier")
    graph.add_conditional_edges(
        "clarifier",
        _route_after_clarifier,
        {
            "await_user": "await_user",
            "planner": "planner",
        },
    )
    graph.add_edge("await_user", END)
    graph.add_edge("planner", "worker_executor")
    graph.add_conditional_edges(
        "worker_executor",
        _route_after_worker,
        {
            "complete": "workers_complete",
            "loop": "worker_executor",
            "blocked": "workers_blocked",
        },
    )
    graph.add_edge("workers_complete", END)
    graph.add_edge("workers_blocked", END)
    return graph.compile()


def run_graph(
    state: WorkflowState,
    registry: dict[str, BaseToolAdapter] | None = None,
) -> WorkflowState:
    compiled = build_graph(registry=registry)
    result = compiled.invoke(to_graph_state(state))
    return from_graph_state(result)
