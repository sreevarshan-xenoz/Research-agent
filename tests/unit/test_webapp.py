from __future__ import annotations

from fastapi.testclient import TestClient

from research_agent.app.webapp import create_app
from research_agent.orchestration.state import WorkflowState


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
        return state


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
