from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from research_agent.orchestration.nodes import (
    awaiting_user_node,
    clarifier_node,
    intake_node,
    planner_node,
)
from research_agent.orchestration.state import GraphState, WorkflowState, from_graph_state, to_graph_state


def _route_after_clarifier(state: GraphState) -> str:
    if state["needs_clarification"] and state["clarification_questions"]:
        return "await_user"
    return "planner"


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("intake", intake_node)
    graph.add_node("clarifier", clarifier_node)
    graph.add_node("await_user", awaiting_user_node)
    graph.add_node("planner", planner_node)

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
    graph.add_edge("planner", END)
    return graph.compile()


def run_graph(state: WorkflowState) -> WorkflowState:
    compiled = build_graph()
    result = compiled.invoke(to_graph_state(state))
    return from_graph_state(result)
