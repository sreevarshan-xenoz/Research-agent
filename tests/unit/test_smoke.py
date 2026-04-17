from pathlib import Path

from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


def test_graph_plans_for_specific_topic(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
    state = WorkflowState(
        run_id="smoke",
        topic="A comparative analysis of retrieval augmentation for software engineering agents",
        artifact_root=str(tmp_path),
    )
    updated = run_graph(state, registry={})
    assert updated.phase == "completed"
    assert updated.stop_reason == "completed"
    assert updated.tasks
    assert all(task.status == "complete" for task in updated.tasks)
    assert updated.artifact_dir
    assert (Path(updated.artifact_dir) / "main.tex").exists()
    assert (Path(updated.artifact_dir) / "references.bib").exists()


def test_graph_routes_to_clarification_for_ambiguous_topic(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
    state = WorkflowState(run_id="smoke", topic="AI", task_findings={})
    updated = run_graph(state, registry={})
    assert updated.phase == "awaiting_user_clarification"
    assert updated.stop_reason == "clarification_required"
    assert len(updated.clarification_questions) >= 2
