from __future__ import annotations

import time

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis import AsyncRedisSaver
import redis.asyncio as redis

from research_agent.orchestration.nodes import (
    awaiting_user_critic_node,
    awaiting_user_node,
    citation_verifier_node,
    clarifier_node,
    combiner_node,
    composer_node,
    critic_node,
    dependency_blocked_node,
    exporter_node,
    figure_generator_node,
    get_pending_task_ids,
    get_ready_task_ids,
    indexing_node,
    intake_node,
    make_worker_node,
    planner_node,
    stop_node,
    workers_complete_node,
)
from research_agent.orchestration.state import GraphState, WorkflowState, from_graph_state, to_graph_state
from research_agent.tools.base import BaseToolAdapter


def _route_after_clarifier(state: GraphState) -> str:
    if state["needs_clarification"] and state["clarification_questions"]:
        return "await_user"
    return "planner"


def _route_after_worker(state: GraphState) -> str:
    stop_reason = _stop_reason(state)
    if stop_reason:
        state["stop_reason"] = stop_reason
        return "stopped"

    tasks = state["tasks"]
    pending = get_pending_task_ids(tasks)
    ready = get_ready_task_ids(tasks)

    if not pending:
        return "complete"
    
    # v2.1: Detect deadlock (pending tasks but none are ready)
    if not ready:
        state["stop_reason"] = "dependency_deadlock"
        return "stopped"
        
    return "loop"


def _route_after_critic(state: GraphState) -> str:
    stop_reason = _stop_reason(state)
    if stop_reason:
        state["stop_reason"] = stop_reason
        return "stopped"

    # If confidence is low and we haven't hit max iterations, loop back
    low_confidence = any(score < 0.35 for score in state["section_confidence"].values())
    
    if low_confidence and state["iteration_index"] < state["max_iterations"]:
        if state.get("autonomy_mode") == "interactive":
            return "await_user_critic"
        return "loop"
    return "combiner"


def _stop_reason(state: GraphState) -> str | None:
    interrupt_sig = state.get("interrupt_signal")  # type: ignore[gpu-or-other]
    if state.get("interrupted") or (interrupt_sig is not None and hasattr(interrupt_sig, "is_set") and interrupt_sig.is_set()):
        return "user_interrupt"

    started_at = float(state.get("started_at", time.time()))
    max_runtime_minutes = int(state.get("max_runtime_minutes", 0) or 0)
    if max_runtime_minutes > 0:
        elapsed_seconds = max(0.0, time.time() - started_at)
        if elapsed_seconds >= (max_runtime_minutes * 60):
            return "runtime_cap_reached"

    max_cost_usd = float(state.get("max_cost_usd", 0.0) or 0.0)
    estimated_cost_usd = float(state.get("estimated_cost_usd", 0.0) or 0.0)
    if max_cost_usd > 0 and estimated_cost_usd >= max_cost_usd:
        return "cost_cap_reached"

    return None


def build_graph(registry: dict[str, BaseToolAdapter] | None = None, checkpointer=None):
    tool_registry = {} if registry is None else registry
    graph = StateGraph(GraphState)
    graph.add_node("intake", intake_node)
    graph.add_node("clarifier", clarifier_node)
    graph.add_node("await_user", awaiting_user_node)
    graph.add_node("planner", planner_node)
    graph.add_node("worker_executor", make_worker_node(tool_registry))
    graph.add_node("workers_complete", workers_complete_node)
    graph.add_node("workers_blocked", dependency_blocked_node)
    graph.add_node("stopped", stop_node)
    graph.add_node("indexing", indexing_node)
    graph.add_node("critic", critic_node)
    graph.add_node("await_user_critic", awaiting_user_critic_node)
    graph.add_node("combiner", combiner_node)
    graph.add_node("figure_generator", figure_generator_node)
    graph.add_node("citation_verifier", citation_verifier_node)
    graph.add_node("composer", composer_node)
    graph.add_node("exporter", exporter_node)

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
            "stopped": "stopped",
        },
    )
    graph.add_edge("workers_complete", "indexing")
    graph.add_edge("workers_blocked", "indexing")
    graph.add_edge("indexing", "critic")

    graph.add_conditional_edges(
        "critic",
        _route_after_critic,
        {
            "await_user_critic": "await_user_critic",
            "loop": "worker_executor",
            "combiner": "combiner",
            "stopped": "stopped",
        },
    )

    graph.add_edge("await_user_critic", END)

    graph.add_edge("stopped", "combiner")
    
    graph.add_edge("combiner", "figure_generator")
    graph.add_edge("figure_generator", "citation_verifier")
    graph.add_edge("citation_verifier", "composer")
    graph.add_edge("composer", "exporter")
    graph.add_edge("exporter", END)
    
    return graph.compile(checkpointer=checkpointer or MemorySaver())


async def run_graph(
    state: WorkflowState,
    registry: dict[str, BaseToolAdapter] | None = None,
    thread_id: str | None = None,
) -> WorkflowState:
    from research_agent.config import load_settings
    settings = load_settings()
    
    checkpointer = None
    redis_conn = None
    
    if settings.features.session_persistence == "redis":
        redis_conn = redis.from_url(settings.redis.url)
        checkpointer = AsyncRedisSaver(redis_client=redis_conn)

    try:
        compiled = build_graph(registry=registry, checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id or state.run_id}}
        result = await compiled.ainvoke(to_graph_state(state), config=config)
        return from_graph_state(result)
    finally:
        if redis_conn:
            await redis_conn.aclose()
