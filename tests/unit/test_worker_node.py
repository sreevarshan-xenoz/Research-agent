from __future__ import annotations

from pathlib import Path

from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState
from research_agent.tools.base import BaseToolAdapter, ToolResult


class FakeAdapter(BaseToolAdapter):
    provider_name = "fake"

    def search(self, query: str, limit: int = 5) -> ToolResult:  # noqa: ARG002
        return ToolResult(
            provider=self.provider_name,
            items=[{"title": "row-1"}, {"title": "row-2"}],
            warnings=["mock-warning"],
        )


def test_worker_executes_ready_tasks_and_stores_findings(tmp_path: Path) -> None:
    state = WorkflowState(
        run_id="worker-smoke",
        topic="Retrieval evaluation methods for coding agents in enterprise settings",
        artifact_root=str(tmp_path),
    )
    registry = {"fake": FakeAdapter()}

    updated = run_graph(state, registry=registry)

    task_status = {task.task_id: task.status for task in updated.tasks}
    assert task_status["t1"] == "complete"
    assert task_status["t2"] == "complete"
    assert task_status["t3"] == "complete"
    assert task_status["t4"] == "complete"

    assert updated.phase == "completed"
    assert updated.stop_reason == "completed"

    assert "t1" in updated.task_findings
    assert "fake" in updated.task_findings["t1"]
    assert updated.task_findings["t1"]["fake"]["item_count"] == 2
    assert updated.task_findings["t1"]["fake"]["warning_count"] == 1
    assert "t4" in updated.task_findings
    assert updated.artifact_dir
    assert (Path(updated.artifact_dir) / "summary.json").exists()
