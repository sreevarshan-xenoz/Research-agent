from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from research_agent.app.webapp import create_app as _create_app
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState
from research_agent.tools.base import BaseToolAdapter, ToolResult
import uuid
from research_agent.app.auth import current_active_user, User

def create_app(*args, **kwargs):
    app = _create_app(*args, **kwargs)
    async def mock_current_active_user() -> User:
        return User(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            hashed_password="...",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
    app.dependency_overrides[current_active_user] = mock_current_active_user
    return app


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
    assert "section_evidence" in payload


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

    # With mocked LLM, the graph runs fallback planner tasks (t1-t4) and
    # workers emit status events via the progress callback
    status_events = [event for event in events if event["event"] == "status"]
    agents_seen = {
        p["agent"]
        for event in status_events
        for p in [event["payload"]]
        if "agent" in p
    }

    assert "SubResearch t1" in agents_seen
    assert "SubResearch t4" in agents_seen
    assert any(event["event"] == "result" for event in events)


# ---------------------------------------------------------------------------
# Trace context restoration tests for FastAPI web endpoints
# ---------------------------------------------------------------------------


def _clean_outer_context() -> None:
    """Reset the trace context var to empty after each test."""
    from research_agent.observability.logging import _trace_id_var as _v
    try:
        _v.set("")
    except Exception:
        pass


def test_chat_endpoint_trace_context_restored() -> None:
    """Verify trace context is properly set/restored inside POST /api/chat.

    Uses a custom TracingRunner that mimics run_graph's context-var behavior:
    sets context on entry, resets on exit. Verifies from both the test's
    perspective (outer context preserved) and inside the endpoint task
    (context was set then restored).
    """
    from research_agent.observability.logging import (
        _trace_id_var as _v,
        get_current_trace_id,
        set_trace_context,
    )

    captured: dict[str, list[str]] = {
        "before_runner": [],
        "inside_runner": [],
        "after_runner": [],
    }

    class TracingRunner:
        """Sync runner that mimics run_graph's context var set/reset."""

        def __call__(self, state: WorkflowState, registry=None) -> WorkflowState:  # noqa: ANN001
            captured["before_runner"].append(get_current_trace_id())
            token = set_trace_context("runner-active")
            captured["inside_runner"].append(get_current_trace_id())
            _v.reset(token)
            captured["after_runner"].append(get_current_trace_id())
            state.phase = "completed"
            state.stop_reason = "completed"
            state.tasks = []
            state.critic_notes = ["ok"]
            state.section_confidence = {"t1": 0.9}
            state.run_warnings = []
            return state

    # --- Round 1: no outer context -----------------------------------------
    app = create_app(graph_runner=TracingRunner(), registry={})
    client = TestClient(app)

    session_resp = client.post("/api/session", json={"template": "ieee"})
    session_id = session_resp.json()["session_id"]

    # Before endpoint call, context is empty
    assert get_current_trace_id() == "", (
        f"Expected empty context before call, got {get_current_trace_id()!r}"
    )

    chat_resp = client.post("/api/chat", json={
        "session_id": session_id,
        "message": "Test context restoration round 1",
        "template": "ieee",
    })
    assert chat_resp.status_code == 200

    # After endpoint call, context is still empty (no outer context was set)
    assert get_current_trace_id() == "", (
        f"Expected empty context after call, got {get_current_trace_id()!r}"
    )

    # Inside the runner, context was set
    assert len(captured["inside_runner"]) == 1
    assert captured["inside_runner"][0] == "runner-active", (
        f"Expected 'runner-active' inside runner, got {captured['inside_runner'][0]!r}"
    )

    # After runner cleanup, context was restored to its pre-runner value
    assert captured["after_runner"][0] == captured["before_runner"][0], (
        f"Context after runner ({captured['after_runner'][0]!r}) should "
        f"match before ({captured['before_runner'][0]!r})"
    )

    # --- Round 2: with outer context ---------------------------------------
    outer_token = set_trace_context("outer-before-chat")
    assert get_current_trace_id() == "outer-before-chat"

    chat_resp2 = client.post("/api/chat", json={
        "session_id": session_id,
        "message": "Test context restoration round 2",
        "template": "ieee",
    })
    assert chat_resp2.status_code == 200

    # Outer context preserved after endpoint returns
    current = get_current_trace_id()
    assert current == "outer-before-chat", (
        f"Expected outer context preserved, got {current!r}"
    )

    # Inside the runner (same task as endpoint), context was set to runner-active
    assert len(captured["inside_runner"]) == 2
    assert captured["inside_runner"][1] == "runner-active", (
        f"Expected 'runner-active' inside runner round 2, "
        f"got {captured['inside_runner'][1]!r}"
    )

    # After runner cleanup, context restored to pre-runner value (outer context)
    assert captured["after_runner"][1] == captured["before_runner"][1], (
        f"Context after runner round 2 ({captured['after_runner'][1]!r}) should "
        f"match before ({captured['before_runner'][1]!r})"
    )
    # The pre-runner context in round 2 should be the outer context
    assert captured["before_runner"][1] == "outer-before-chat", (
        f"Expected outer context before runner round 2, "
        f"got {captured['before_runner'][1]!r}"
    )

    _v.reset(outer_token)
    _clean_outer_context()


def _make_async_tracing_runner(
    captured: dict[str, list[str]],
) -> WorkflowState:
    """Create an async runner function that captures trace context at key points.

    Using a plain async function instead of a class with async __call__
    ensures that asyncio.iscoroutinefunction() correctly identifies it.
    """
    from research_agent.observability.logging import (
        _trace_id_var as _v,
        get_current_trace_id,
        set_trace_context,
    )

    async def _runner(state: WorkflowState, registry=None) -> WorkflowState:  # noqa: ANN001
        captured["before_runner"].append(get_current_trace_id())
        token = set_trace_context("stream-runner-active")
        captured["inside_runner"].append(get_current_trace_id())
        _v.reset(token)
        captured["after_runner"].append(get_current_trace_id())
        state.phase = "completed"
        state.stop_reason = "completed"
        state.tasks = []
        state.critic_notes = ["ok"]
        state.section_confidence = {"t1": 0.9}
        state.run_warnings = []
        return state

    return _runner


def _make_failing_runner(
    captured_inside: list[str],
    captured_after: list[str],
) -> WorkflowState:
    """Create an async runner that sets context then raises."""
    from research_agent.observability.logging import (
        _trace_id_var as _v,
        get_current_trace_id,
        set_trace_context,
    )

    async def _runner(state: WorkflowState, registry=None) -> WorkflowState:  # noqa: ANN001
        token = set_trace_context("about-to-fail")
        captured_inside.append(get_current_trace_id())
        _v.reset(token)
        captured_after.append(get_current_trace_id())
        raise RuntimeError("Simulated failure inside runner")

    return _runner


def test_chat_stream_endpoint_trace_context_restored() -> None:
    """Verify trace context is properly set/restored inside POST /api/chat/stream.

    The streaming endpoint runs the graph in a background asyncio.create_task.
    This test verifies context var propagation across that boundary.
    """
    captured: dict[str, list[str]] = {
        "before_runner": [],
        "inside_runner": [],
        "after_runner": [],
    }
    tracing_runner = _make_async_tracing_runner(captured)

    app = create_app(graph_runner=tracing_runner, registry={})
    client = TestClient(app)

    session_resp = client.post("/api/session", json={"template": "ieee"})
    assert session_resp.status_code == 200
    session_id = session_resp.json()["session_id"]

    # --- Round 1: no outer context -----------------------------------------
    from research_agent.observability.logging import (
        _trace_id_var as _v,
        get_current_trace_id,
        set_trace_context,
    )

    assert get_current_trace_id() == "", (
        f"Expected empty context before stream, got {get_current_trace_id()!r}"
    )

    stream_resp = client.post("/api/chat/stream", json={
        "session_id": session_id,
        "message": "Test stream context round 1",
        "template": "ieee",
    })
    assert stream_resp.status_code == 200

    # Drain stream fully
    for line in stream_resp.iter_lines():
        if not line:
            continue

    # Context remains empty (no outer context was set)
    assert get_current_trace_id() == "", (
        f"Expected empty context after stream, got {get_current_trace_id()!r}"
    )

    assert len(captured["inside_runner"]) == 1, (
        f"Runner was not executed. captured={captured}"
    )
    assert captured["inside_runner"][0] == "stream-runner-active", (
        f"Expected 'stream-runner-active' inside runner, "
        f"got {captured['inside_runner'][0]!r}"
    )
    assert captured["after_runner"][0] == captured["before_runner"][0]

    # --- Round 2: with outer context ---------------------------------------
    outer_token = set_trace_context("outer-before-stream")
    assert get_current_trace_id() == "outer-before-stream"

    stream_resp2 = client.post("/api/chat/stream", json={
        "session_id": session_id,
        "message": "Test stream context round 2",
        "template": "ieee",
    })
    assert stream_resp2.status_code == 200

    for line in stream_resp2.iter_lines():
        if not line:
            continue

    # Outer context preserved
    current = get_current_trace_id()
    assert current == "outer-before-stream", (
        f"Expected outer context preserved after stream, got {current!r}"
    )

    assert len(captured["inside_runner"]) == 2, (
        f"Runner was not executed in round 2. captured={captured}"
    )
    assert captured["inside_runner"][1] == "stream-runner-active"
    assert captured["after_runner"][1] == captured["before_runner"][1]
    assert captured["before_runner"][1] == "outer-before-stream", (
        f"Expected outer context inside stream runner, "
        f"got {captured['before_runner'][1]!r}"
    )

    _v.reset(outer_token)
    _clean_outer_context()


def test_chat_endpoint_trace_context_restored_after_error() -> None:
    """Verify trace context is restored even when the runner raises an error."""
    from research_agent.observability.logging import (
        _trace_id_var as _v,
        get_current_trace_id,
        set_trace_context,
    )

    captured_inside: list[str] = []
    captured_after: list[str] = []
    failing_runner = _make_failing_runner(captured_inside, captured_after)

    app = create_app(graph_runner=failing_runner, registry={})
    client = TestClient(app)

    session_resp = client.post("/api/session", json={"template": "ieee"})
    assert session_resp.status_code == 200
    session_id = session_resp.json()["session_id"]

    # Without outer context
    chat_resp = client.post("/api/chat", json={
        "session_id": session_id,
        "message": "Test error context",
        "template": "ieee",
    })
    # Endpoint catches and returns 500
    assert chat_resp.status_code == 500

    # Context restored to empty
    assert get_current_trace_id() == "", (
        f"Expected empty context after error, got {get_current_trace_id()!r}"
    )
    assert len(captured_inside) > 0, "Runner was not executed"
    assert captured_inside[0] == "about-to-fail"
    assert captured_after[0] == ""  # default/initial after reset

    # With outer context
    outer_token = set_trace_context("outer-before-error")
    assert get_current_trace_id() == "outer-before-error"

    chat_resp2 = client.post("/api/chat", json={
        "session_id": session_id,
        "message": "Test error context with outer",
        "template": "ieee",
    })
    assert chat_resp2.status_code == 500

    current = get_current_trace_id()
    assert current == "outer-before-error", (
        f"Expected outer context preserved after error, got {current!r}"
    )
    assert len(captured_inside) > 1, "Runner was not executed in round 2"
    assert captured_inside[1] == "about-to-fail"
    # After runner cleanup, context was restored to outer value
    assert captured_after[1] == "outer-before-error", (
        f"Expected outer context after runner cleanup, "
        f"got {captured_after[1]!r}"
    )

    _v.reset(outer_token)
    _clean_outer_context()


@pytest.mark.asyncio
async def test_chat_endpoint_context_restored_with_real_run_graph() -> None:
    """Verify trace context restoration through POST /api/chat with real run_graph.

    Uses the actual run_graph function with stubbed critic and combiner nodes
    to exercise the real set_trace_context/reset_trace_context call pair.
    """
    from unittest.mock import patch

    from research_agent.orchestration.graph import run_graph
    from research_agent.orchestration.state import WorkflowState

    from tests.unit.test_trace_context import (
        _stub_critic_node,
        _stub_combiner_node,
    )

    app = create_app(graph_runner=run_graph, registry={})
    client = TestClient(app)

    session_resp = client.post("/api/session", json={"template": "ieee"})
    session_id = session_resp.json()["session_id"]

    # Apply stubs so run_graph can complete without real LLM calls
    with patch(
        "research_agent.orchestration.graph.critic_node", _stub_critic_node
    ), patch(
        "research_agent.orchestration.graph.combiner_node", _stub_combiner_node
    ):
        chat_resp = client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Context restoration test via real run_graph",
            "template": "ieee",
        })

    # Endpoint should complete successfully (run_graph restored context)
    assert chat_resp.status_code == 200, (
        f"Expected 200 OK, got {chat_resp.status_code}: {chat_resp.text}"
    )

    payload = chat_resp.json()
    assert payload["kind"] in ("result", "clarification"), (
        f"Expected 'result' or 'clarification', got {payload['kind']!r}"
    )

    # Trace context restored to empty after run_graph completes via endpoint
    from research_agent.observability.logging import get_current_trace_id
    current = get_current_trace_id()
    assert current == "", (
        f"Expected empty context after real run_graph via endpoint, got {current!r}"
    )


@pytest.mark.asyncio
async def test_chat_stream_endpoint_context_restored_with_real_run_graph() -> None:
    """Verify trace context restoration through POST /api/chat/stream with real run_graph.

    The streaming endpoint runs run_graph in a background task. This test ensures
    that the context var is properly set/reset even across task boundaries.
    """
    from unittest.mock import patch

    from research_agent.orchestration.graph import run_graph

    from tests.unit.test_trace_context import (
        _stub_critic_node,
        _stub_combiner_node,
    )

    app = create_app(graph_runner=run_graph, registry={})
    client = TestClient(app)

    session_resp = client.post("/api/session", json={"template": "ieee"})
    session_id = session_resp.json()["session_id"]

    with patch(
        "research_agent.orchestration.graph.critic_node", _stub_critic_node
    ), patch(
        "research_agent.orchestration.graph.combiner_node", _stub_combiner_node
    ):
        stream_resp = client.post("/api/chat/stream", json={
            "session_id": session_id,
            "message": "Stream context restoration test via real run_graph",
            "template": "ieee",
        })

    assert stream_resp.status_code == 200, (
        f"Expected 200 OK, got {stream_resp.status_code}"
    )

    # Drain the stream to completion
    events = []
    for line in stream_resp.iter_lines():
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        events.append(json.loads(line))

    # Stream should have completed (None sentinel sent)
    assert any(event["event"] == "result" for event in events), (
        f"Stream completed without 'result' event. Events: {[e['event'] for e in events]}"
    )

    # Trace context restored to empty after stream completes
    from research_agent.observability.logging import get_current_trace_id
    current = get_current_trace_id()
    assert current == "", (
        f"Expected empty context after stream with real run_graph, got {current!r}"
    )


def test_webapp_resume_returns_last_checkpoint(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("CHECKPOINT_ROOT", str(tmp_path / "checkpoints"))
    monkeypatch.setenv("RUN_EVENT_ROOT", str(tmp_path / "events"))

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

    second_chat = client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "message": "Focus on CI pipeline code review agents.",
            "template": "ieee",
        },
    )
    assert second_chat.status_code == 200
    assert second_chat.json()["kind"] == "result"

    resume = client.post(f"/api/session/{session_id}/resume")
    assert resume.status_code == 200
    payload = resume.json()
    assert payload["kind"] == "result"
    assert payload["run_id"] == second_chat.json()["run_id"]
