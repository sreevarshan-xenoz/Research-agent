from __future__ import annotations

from pathlib import Path

import pytest

from research_agent.observability import progress_callback
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.nodes.worker import make_worker_node
from research_agent.orchestration.state import GraphState, WorkflowState
from research_agent.tools.base import BaseToolAdapter, ToolResult


class FakeAdapter(BaseToolAdapter):
    provider_name = "fake"

    def search(self, query: str, limit: int = 5) -> ToolResult:  # noqa: ARG002
        return ToolResult(
            provider=self.provider_name,
            items=[{"title": "row-1"}, {"title": "row-2"}],
            warnings=["mock-warning"],
        )


class FakeWebAdapter(BaseToolAdapter):
    provider_name = "duckduckgo"

    def search(self, query: str, limit: int = 5) -> ToolResult:  # noqa: ARG002
        return ToolResult(
            provider=self.provider_name,
            items=[
                {
                    "title": "Web result",
                    "url": "https://example.com/result",
                    "snippet": "Short snippet",
                    "source_type": "web",
                }
            ],
        )


class FakePageFetcher(BaseToolAdapter):
    provider_name = "page_fetcher"
    is_searcher = False

    def search(self, query: str, limit: int = 1) -> ToolResult:  # noqa: ARG002
        return ToolResult(
            provider=self.provider_name,
            items=[
                {
                    "title": "Fetched page",
                    "url": query,
                    "content": "Cleaned full page content.",
                    "source_type": "web_page",
                }
            ],
        )


@pytest.mark.asyncio
async def test_worker_executes_ready_tasks_and_stores_findings(
    tmp_path: Path,
    monkeypatch,  # noqa: ANN001
) -> None:
    monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
    state = WorkflowState(
        run_id="worker-smoke",
        topic="Retrieval evaluation methods for coding agents in enterprise settings",
        artifact_root=str(tmp_path),
    )
    registry = {"fake": FakeAdapter()}

    updated = await run_graph(state, registry=registry)

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


@pytest.mark.asyncio
async def test_worker_node_emits_real_task_progress() -> None:
    state: GraphState = {
        "run_id": "worker-progress",
        "topic": "Agent evaluation",
        "template": "ieee",
        "phase": "planned",
        "iteration_index": 0,
        "stop_reason": None,
        "tasks": [
        {
            "task_id": "t1",
            "title": "Background",
            "objective": "Collect background",
            "depends_on": [],
            "status": "pending",
        },
        {
            "task_id": "t2",
            "title": "Analysis",
            "objective": "Analyze methods",
            "depends_on": ["t1"],
            "status": "pending",
        },
        ],
        "section_confidence": {},
        "clarification_questions": [],
        "needs_clarification": False,
        "task_findings": {},
        "critic_notes": [],
        "combined_sections": [],
        "citations": [],
        "latex_main": "",
        "bibtex": "",
        "artifact_root": "artifacts",
        "artifact_dir": "",
        "run_warnings": [],
    }
    events: list[dict[str, str]] = []
    worker = make_worker_node({"fake": FakeAdapter()})

    with progress_callback(events.append):
        result = await worker(state)

    assert result["tasks"][0]["status"] == "complete"
    assert result["tasks"][1]["status"] == "pending"
    assert events == [
        {
            "agent": "SubResearch t1",
            "status": "running",
            "detail": "Background",
            "message": "Running t1",
        },
        {
            "agent": "SubResearch t1",
            "status": "complete",
            "detail": "Background (2 items)",
            "message": "Completed t1",
        },
    ]


@pytest.mark.asyncio
async def test_worker_enriches_web_results_with_page_fetcher() -> None:
    state: GraphState = {
        "run_id": "worker-fetch",
        "topic": "Agent evaluation",
        "template": "ieee",
        "phase": "planned",
        "iteration_index": 0,
        "stop_reason": None,
        "tasks": [
            {
                "task_id": "t1",
                "title": "Background",
                "objective": "Collect background",
                "depends_on": [],
                "status": "pending",
                "providers": ["duckduckgo"],
            }
        ],
        "section_confidence": {},
        "clarification_questions": [],
        "needs_clarification": False,
        "task_findings": {},
        "critic_notes": [],
        "combined_sections": [],
        "citations": [],
        "latex_main": "",
        "bibtex": "",
        "artifact_root": "artifacts",
        "artifact_dir": "",
        "run_warnings": [],
    }
    worker = make_worker_node({"duckduckgo": FakeWebAdapter(), "page_fetcher": FakePageFetcher()})

    result = await worker(state)

    item = result["task_findings"]["t1"]["duckduckgo"]["items"][0]
    assert item["content"] == "Cleaned full page content."
