from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


def test_graph_plans_for_specific_topic() -> None:
    state = WorkflowState(
        run_id="smoke",
        topic="A comparative analysis of retrieval augmentation for software engineering agents",
    )
    updated = run_graph(state)
    assert updated.phase == "planned"
    assert updated.tasks


def test_graph_routes_to_clarification_for_ambiguous_topic() -> None:
    state = WorkflowState(run_id="smoke", topic="AI")
    updated = run_graph(state)
    assert updated.phase == "awaiting_user_clarification"
    assert updated.stop_reason == "clarification_required"
    assert len(updated.clarification_questions) >= 2
