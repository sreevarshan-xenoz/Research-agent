from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


def test_graph_scaffold_runs() -> None:
    state = WorkflowState(run_id="smoke", topic="test topic")
    updated = run_graph(state)
    assert updated.phase == "scaffold"
