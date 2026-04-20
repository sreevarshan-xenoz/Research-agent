from __future__ import annotations

from research_agent.orchestration.state import GraphState


async def workers_complete_node(state: GraphState) -> dict:
    return {
        "phase": "workers_complete",
        "stop_reason": "worker_execution_complete",
    }


async def dependency_blocked_node(state: GraphState) -> dict:
    return {
        "phase": "workers_blocked",
        "stop_reason": "dependency_blocked",
    }


async def stop_node(state: GraphState) -> dict:
    return {
        "phase": "stopped",
        "stop_reason": state.get("stop_reason") or "stopped",
    }
