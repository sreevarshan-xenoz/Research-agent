from __future__ import annotations

from research_agent.orchestration.state import WorkflowState


def run_graph(state: WorkflowState) -> WorkflowState:
    """Temporary orchestration placeholder for initial scaffold.

    Replace this with LangGraph node wiring in implementation phase.
    """
    state.phase = "scaffold"
    return state
