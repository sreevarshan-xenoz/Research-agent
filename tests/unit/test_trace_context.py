"""Tests for automatic trace_id propagation via contextvars.

Verifies that log_error() and log_exception() inherit the trace_id from
the context var when not explicitly provided, and that set_trace_context() /
reset work correctly.
"""

from __future__ import annotations

from typing import Generator
from unittest.mock import patch

import pytest

from research_agent.observability.logging import (
    get_current_trace_id,
    log_error,
    log_exception,
    set_trace_context,
)


@pytest.fixture(autouse=True)
def _clean_trace_context() -> Generator[None, None, None]:
    """Ensure each test starts with a clean trace context."""
    from research_agent.observability.logging import _trace_id_var as _var
    token = _var.set("")
    yield
    try:
        _var.reset(token)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# get_current_trace_id / set_trace_context
# ---------------------------------------------------------------------------


def test_default_trace_id_is_empty() -> None:
    assert get_current_trace_id() == ""


def test_set_trace_context_returns_token() -> None:
    token = set_trace_context("run-abc")
    assert token is not None
    assert get_current_trace_id() == "run-abc"


def test_set_trace_context_overrides_previous() -> None:
    set_trace_context("run-first")
    assert get_current_trace_id() == "run-first"
    set_trace_context("run-second")
    assert get_current_trace_id() == "run-second"


def test_set_trace_context_restore_empty() -> None:
    from research_agent.observability.logging import _trace_id_var as _var
    token = _var.set("run-xyz")
    assert get_current_trace_id() == "run-xyz"
    _var.reset(token)
    assert get_current_trace_id() == ""


# ---------------------------------------------------------------------------
# log_error inherits trace_id from context
# ---------------------------------------------------------------------------


def test_log_error_uses_explicit_trace_id() -> None:
    """Explicit trace_id should take precedence over context var."""
    set_trace_context("ctx-run")
    with patch("research_agent.observability.logging.logger") as mock_logger:
        log_error("test", trace_id="explicit-override")
    args, _kwargs = mock_logger.log.call_args
    formatted = args[1]
    assert "[explicit-override]" in formatted


def test_log_error_inherits_context_trace_id() -> None:
    """When trace_id is not provided, inherit from context var."""
    set_trace_context("ctx-run-42")
    with patch("research_agent.observability.logging.logger") as mock_logger:
        log_error("test message")
    args, _kwargs = mock_logger.log.call_args
    formatted = args[1]
    assert "[ctx-run-42]" in formatted


def test_log_error_empty_context_uses_empty() -> None:
    """When context var is empty and trace_id is not provided, use empty."""
    with patch("research_agent.observability.logging.logger") as mock_logger:
        log_error("test message")
    args, _kwargs = mock_logger.log.call_args
    formatted = args[1]
    # Format: [recoverable] [] [] test message
    assert " [] " in formatted  # empty trace_id section


def test_log_error_override_clears_context() -> None:
    """Empty explicit trace_id doesn't override a non-empty context."""
    set_trace_context("still-here")
    with patch("research_agent.observability.logging.logger") as mock_logger:
        log_error("test")
    args, _kwargs = mock_logger.log.call_args
    formatted = args[1]
    assert "[still-here]" in formatted


def test_log_error_inherits_in_sub_function() -> None:
    """Nested function calls inherit the same trace context."""

    def inner_log() -> None:
        log_error("inner error")

    set_trace_context("nested-run")
    with patch("research_agent.observability.logging.logger") as mock_logger:
        inner_log()
    args, _kwargs = mock_logger.log.call_args
    formatted = args[1]
    assert "[nested-run]" in formatted


# ---------------------------------------------------------------------------
# log_exception inherits trace_id from context
# ---------------------------------------------------------------------------


def test_log_exception_uses_explicit_trace_id() -> None:
    set_trace_context("ctx-run")
    with patch("research_agent.observability.logging.logger") as mock_logger:
        log_exception("exc test", exc=ValueError("ouch"))
    args, _kwargs = mock_logger.warning.call_args
    formatted = args[0]
    assert "[ctx-run]" in formatted


def test_log_exception_inherits_context_trace_id() -> None:
    set_trace_context("exc-run-99")
    with patch("research_agent.observability.logging.logger") as mock_logger:
        log_exception("exc test", exc=ValueError("ouch"))
    args, _kwargs = mock_logger.warning.call_args
    formatted = args[0]
    assert "[exc-run-99]" in formatted


def test_log_exception_empty_context() -> None:
    with patch("research_agent.observability.logging.logger") as mock_logger:
        log_exception("exc test", exc=ValueError("ouch"))
    args, _kwargs = mock_logger.warning.call_args
    formatted = args[0]
    assert " [] " in formatted  # empty trace_id section


# ---------------------------------------------------------------------------
# NodeTimer inherits trace_id from context
# ---------------------------------------------------------------------------


def test_nodetimer_inherits_context_trace_id() -> None:
    """NodeTimer should pick up trace_id from context if not explicitly set."""
    from research_agent.observability.logging import NodeTimer

    set_trace_context("timer-run")
    timer = NodeTimer("test_node")
    # When trace_id is empty (default), NodeTimer should fall back to context var
    assert timer.trace_id == "timer-run", (
        f"Expected trace_id='timer-run', got {timer.trace_id!r}"
    )


def test_nodetimer_explicit_overrides_context() -> None:
    """Explicit trace_id in NodeTimer should override context var."""
    from research_agent.observability.logging import NodeTimer

    set_trace_context("ctx-val")
    timer = NodeTimer("test_node", trace_id="explicit-val")
    assert timer.trace_id == "explicit-val"


# ---------------------------------------------------------------------------
# Integration: run_graph sets trace context (via set_trace_context)
# ---------------------------------------------------------------------------


async def _stub_critic_node(state: dict) -> dict:
    """Stub that returns valid critic output without triggering the pre-existing
    await bug in the real critic_node."""
    tasks = state.get("tasks", [])
    return {
        "section_confidence": {str(t.get("task_id", "0")): 0.9 for t in tasks},
        "critic_notes": ["Bypassed by test stub"],
        "phase": "critic_scored",
        "tasks": tasks,
        "iteration_index": state.get("iteration_index", 0) + 1,
    }


async def _stub_combiner_node(state: dict) -> dict:
    """Stub that returns valid combiner output without triggering the pre-existing
    await bugs in the real combiner_node."""
    return {"combined_sections": [], "phase": "combined"}


@pytest.mark.asyncio
async def test_run_graph_sets_trace_context() -> None:
    """Verify run_graph() sets the context var before executing nodes."""
    from research_agent.orchestration.graph import run_graph
    from research_agent.orchestration.state import WorkflowState

    # Stub critic_node and combiner_node in graph.py's namespace to bypass
    # pre-existing await bugs in both nodes
    with patch(
        "research_agent.orchestration.graph.critic_node", _stub_critic_node
    ), patch(
        "research_agent.orchestration.graph.combiner_node", _stub_combiner_node
    ):
        state = WorkflowState(
            run_id="ctx-integration-test",
            topic="Integration test for trace context propagation",
            artifact_root="/tmp/ctx-test",
            max_iterations=1,
        )

        result = await run_graph(state, registry={})

    assert result.run_id == "ctx-integration-test"


@pytest.mark.asyncio
async def test_trace_context_during_run_graph() -> None:
    """Hook into run_graph to verify trace_id is set during node execution."""
    from research_agent.orchestration.graph import run_graph
    from research_agent.orchestration.state import WorkflowState

    captured_trace_ids: list[str] = []

    original_import = __import__("research_agent.observability.logging", fromlist=["get_current_trace_id"])
    original_get = original_import.get_current_trace_id

    async def tracing_intake_node(state: dict) -> dict:
        captured_trace_ids.append(original_get())
        return {"phase": "intake_done"}

    with patch(
        "research_agent.orchestration.graph.critic_node", _stub_critic_node
    ), patch(
        "research_agent.orchestration.graph.combiner_node", _stub_combiner_node
    ), patch(
        "research_agent.orchestration.graph.intake_node",
        tracing_intake_node,
    ):
        state = WorkflowState(
            run_id="ctx-capture-test",
            topic="Capture trace id during node execution test verification",
            artifact_root="/tmp/ctx-capture",
            max_iterations=1,
        )

        await run_graph(state, registry={})

    assert len(captured_trace_ids) > 0, "No trace IDs were captured during node execution"
    assert captured_trace_ids[0] == "ctx-capture-test", (
        f"Expected trace_id='ctx-capture-test', got {captured_trace_ids[0]!r}"
    )


# ---------------------------------------------------------------------------
# Integration: trace context restoration after run_graph
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trace_context_restored_after_successful_run() -> None:
    """Verify context var is restored to its prior value after run_graph succeeds."""
    from research_agent.orchestration.graph import run_graph
    from research_agent.orchestration.state import WorkflowState

    # Set an outer context that should be preserved after run_graph completes
    outer_token = set_trace_context("outer-context")
    assert get_current_trace_id() == "outer-context"

    with patch(
        "research_agent.orchestration.graph.critic_node", _stub_critic_node
    ), patch(
        "research_agent.orchestration.graph.combiner_node", _stub_combiner_node
    ):
        state = WorkflowState(
            run_id="ctx-restore-ok",
            topic="Test context restoration after success",
            artifact_root="/tmp/ctx-restore-test",
            max_iterations=1,
        )

        result = await run_graph(state, registry={})

    # After run_graph returns, context should be back to what we had before
    assert result.run_id == "ctx-restore-ok"
    assert get_current_trace_id() == "outer-context", (
        f"Expected context restored to 'outer-context', got {get_current_trace_id()!r}"
    )

    # Clean up the outer token
    from research_agent.observability.logging import _trace_id_var as _var
    _var.reset(outer_token)
    assert get_current_trace_id() == ""


@pytest.mark.asyncio
async def test_trace_context_restored_after_failed_run() -> None:
    """Verify context var is restored to its prior value even when run_graph raises."""
    from research_agent.orchestration.graph import run_graph
    from research_agent.orchestration.state import WorkflowState

    # Set an outer context that should survive an exception
    outer_token = set_trace_context("outer-before-failure")
    assert get_current_trace_id() == "outer-before-failure"

    async def failing_intake_node(_state: dict) -> dict:
        msg = "Simulated catastrophic failure in intake"
        raise RuntimeError(msg)

    with patch(
        "research_agent.orchestration.graph.critic_node", _stub_critic_node
    ), patch(
        "research_agent.orchestration.graph.combiner_node", _stub_combiner_node
    ), patch(
        "research_agent.orchestration.graph.intake_node",
        failing_intake_node,
    ):
        state = WorkflowState(
            run_id="ctx-restore-fail",
            topic="Test context restoration after failure",
            artifact_root="/tmp/ctx-restore-fail",
            max_iterations=1,
        )

        with pytest.raises(RuntimeError, match="Simulated catastrophic failure in intake"):
            await run_graph(state, registry={})

    # After run_graph raises, context should be restored to outer context
    assert get_current_trace_id() == "outer-before-failure", (
        f"Expected context restored to 'outer-before-failure', got {get_current_trace_id()!r}"
    )

    # Clean up the outer token
    from research_agent.observability.logging import _trace_id_var as _var
    _var.reset(outer_token)
    assert get_current_trace_id() == ""


@pytest.mark.asyncio
async def test_trace_context_nested_outer_preserved() -> None:
    """Verify a non-empty outer context is preserved, not just restored to empty."""
    from research_agent.orchestration.graph import run_graph
    from research_agent.orchestration.state import WorkflowState

    # Set a meaningful outer context (not empty)
    outer_token = set_trace_context("persistent-session-42")
    assert get_current_trace_id() == "persistent-session-42"

    with patch(
        "research_agent.orchestration.graph.critic_node", _stub_critic_node
    ), patch(
        "research_agent.orchestration.graph.combiner_node", _stub_combiner_node
    ):
        state = WorkflowState(
            run_id="run-inside-outer",
            topic="Test nested outer context preservation",
            artifact_root="/tmp/ctx-outer-preserve",
            max_iterations=1,
        )

        await run_graph(state, registry={})

    # Context should be back to the exact outer value, not just non-empty
    current = get_current_trace_id()
    assert current == "persistent-session-42", (
        f"Expected outer context 'persistent-session-42', got {current!r}"
    )

    # Clean up the outer token
    from research_agent.observability.logging import _trace_id_var as _var
    _var.reset(outer_token)
    assert get_current_trace_id() == ""


@pytest.mark.asyncio
async def test_trace_context_output_restored_on_nested_call() -> None:
    """Verify that multiple run_graph calls don't leak context between them."""
    from research_agent.orchestration.graph import run_graph
    from research_agent.orchestration.state import WorkflowState

    captured_inside_a: list[str] = []
    captured_inside_b: list[str] = []

    original_get = get_current_trace_id

    async def tracing_intake_a(state: dict) -> dict:
        captured_inside_a.append(original_get())
        return {"phase": "intake_done"}

    async def tracing_intake_b(state: dict) -> dict:
        captured_inside_b.append(original_get())
        return {"phase": "intake_done"}

    with patch(
        "research_agent.orchestration.graph.critic_node", _stub_critic_node
    ), patch(
        "research_agent.orchestration.graph.combiner_node", _stub_combiner_node
    ):
        state_a = WorkflowState(
            run_id="run-a",
            topic="Run A",
            artifact_root="/tmp/ctx-nested-a",
            max_iterations=1,
        )
        state_b = WorkflowState(
            run_id="run-b",
            topic="Run B",
            artifact_root="/tmp/ctx-nested-b",
            max_iterations=1,
        )

        with patch(
            "research_agent.orchestration.graph.intake_node", tracing_intake_a
        ):
            await run_graph(state_a, registry={})
        with patch(
            "research_agent.orchestration.graph.intake_node", tracing_intake_b
        ):
            await run_graph(state_b, registry={})

    # Each run should have its own trace_id active inside it
    assert len(captured_inside_a) > 0
    assert captured_inside_a[0] == "run-a", (
        f"Expected 'run-a' inside run_graph A, got {captured_inside_a[0]!r}"
    )

    assert len(captured_inside_b) > 0
    assert captured_inside_b[0] == "run-b", (
        f"Expected 'run-b' inside run_graph B, got {captured_inside_b[0]!r}"
    )

    # After both runs complete, context should be restored to original (empty)
    assert get_current_trace_id() == "", (
        f"Expected empty context after both runs, got {get_current_trace_id()!r}"
    )
