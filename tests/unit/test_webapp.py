from __future__ import annotations

import json

from fastapi.testclient import TestClient

from research_agent.app.webapp import create_app
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState
from research_agent.tools.base import BaseToolAdapter, ToolResult


class FakeRunner:
    def __init__(self) -> None:
        self.call_count = 0

    def __call__(self, state: WorkflowState, registry=None) -> WorkflowState:  # noqa: ANN001
        self.call_count += 1

        if self.call_count == 1:
            state.phase = "awaiting_user_clarification"
            state.clarification_questions = [
                "What exact scope should this research focus on?",
                "What depth do you want?",
            ]
            state.stop_reason = "clarification_required"
            return state

        state.phase = "completed"
        state.stop_reason = "completed"
        state.tasks = []
        state.critic_notes = ["ok"]
        state.section_confidence = {"t1": 0.9}
        state.run_warnings = []
        state.latex_main = "\\begin{document}\n\\section{Intro}\nHello world.\n\\end{document}"
        return state


class FakeAdapter(BaseToolAdapter):
    provider_name = "fake"

    def search(self, query: str, limit: int = 5) -> ToolResult:  # noqa: ARG002
        return ToolResult(provider=self.provider_name, items=[{"title": "row-1"}, {"title": "row-2"}])


def test_webapp_session_and_clarification_flow() -> None:
    app = create_app(graph_runner=FakeRunner(), registry={})
    client = TestClient(app)

    session_response = client.post("/api/session", json={"template": "ieee"})
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    first_chat = client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "message": "AI",
            "template": "ieee",
        },
    )
    assert first_chat.status_code == 200
    assert first_chat.json()["kind"] == "clarification"
    assert len(first_chat.json()["questions"]) == 2

    second_chat = client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "message": "Focus on CI pipeline code review agents.",
            "template": "ieee",
        },
    )
    assert second_chat.status_code == 200
    payload = second_chat.json()
    assert payload["kind"] == "result"
    assert payload["run_id"] is not None


def test_webapp_index_and_health() -> None:
    app = create_app(graph_runner=FakeRunner(), registry={})
    client = TestClient(app)

    index_response = client.get("/")
    assert index_response.status_code == 200
    assert "Research Agent Web" in index_response.text

    health_response = client.get("/api/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"


def test_webapp_stream_endpoint() -> None:
    app = create_app(graph_runner=FakeRunner(), registry={})
    client = TestClient(app)

    session_response = client.post("/api/session", json={"template": "ieee"})
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    clarification_stream = client.post(
        "/api/chat/stream",
        json={
            "session_id": session_id,
            "message": "AI",
            "template": "ieee",
        },
    )
    assert clarification_stream.status_code == 200

    clarification_events = []
    for line in clarification_stream.iter_lines():
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        clarification_events.append(json.loads(line))

    assert any(event["event"] == "clarification" for event in clarification_events)

    result_stream = client.post(
        "/api/chat/stream",
        json={
            "session_id": session_id,
            "message": "Focus on CI pipeline code review agents.",
            "template": "ieee",
        },
    )
    assert result_stream.status_code == 200

    result_events = []
    for line in result_stream.iter_lines():
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        result_events.append(json.loads(line))

    assert any(event["event"] == "latex_chunk" for event in result_events)
    assert any(event["event"] == "result" for event in result_events)


def test_webapp_stream_reports_real_subagent_progress(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
    app = create_app(graph_runner=run_graph, registry={"fake": FakeAdapter()})
    client = TestClient(app)

    session_response = client.post("/api/session", json={"template": "ieee"})
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    result_stream = client.post(
        "/api/chat/stream",
        json={
            "session_id": session_id,
            "message": "Retrieval evaluation methods for coding agents",
            "template": "ieee",
        },
    )
    assert result_stream.status_code == 200

    events = []
    for line in result_stream.iter_lines():
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        events.append(json.loads(line))

    status_events = [event for event in events if event["event"] == "status"]
    flattened_agents = [
        agent["name"]
        for event in status_events
        for agent in event["payload"].get("agent_activity", [])
    ]

    assert "SubResearch t1" in flattened_agents
    assert "SubResearch t4" in flattened_agents
    assert any(event["event"] == "result" for event in events)
