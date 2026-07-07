"""Tests for graph routing functions with autonomy_mode considerations.

Covers:
- _route_after_worker: stop reasons, task completion, deadlock, loop
- _route_after_critic: stop reasons, autonomy_mode routing, max iterations
"""

import pytest
import time
from research_agent.orchestration.graph import _route_after_worker, _route_after_critic, build_graph


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def worker_base_state():
    """Minimal state dict for _route_after_worker tests."""
    return {
        "run_id": "test-run",
        "interrupted": False,
        "interrupt_signal": None,
        "started_at": time.time(),
        "max_runtime_minutes": 0,
        "max_cost_usd": 0.0,
        "estimated_cost_usd": 0.0,
        "stop_reason": None,
        "tasks": [],
    }


@pytest.fixture
def critic_base_state():
    """Minimal state dict for _route_after_critic tests."""
    return {
        "run_id": "test-run",
        "interrupted": False,
        "interrupt_signal": None,
        "started_at": time.time(),
        "max_runtime_minutes": 0,
        "max_cost_usd": 0.0,
        "estimated_cost_usd": 0.0,
        "stop_reason": None,
        "section_confidence": {},
        "iteration_index": 0,
        "max_iterations": 4,
        "autonomy_mode": "hybrid",
        "run_warnings": [],
    }


def _make_task(task_id: str, status: str = "pending", depends_on: list[str] | None = None):
    return {
        "task_id": task_id,
        "title": f"Task {task_id}",
        "objective": f"Objective {task_id}",
        "depends_on": depends_on or [],
        "status": status,
    }


# ── _route_after_worker: Stop Reason Tests ──────────────────────────────────

class TestRouteAfterWorkerStopReasons:
    def test_user_interrupt_via_interrupted_flag(self, worker_base_state):
        state = dict(worker_base_state)
        state["interrupted"] = True
        assert _route_after_worker(state) == "stopped"
        assert state["stop_reason"] == "user_interrupt"

    def test_runtime_cap_reached(self, worker_base_state):
        state = dict(worker_base_state)
        state["max_runtime_minutes"] = 1
        state["started_at"] = time.time() - 120  # 2 minutes ago
        assert _route_after_worker(state) == "stopped"
        assert state["stop_reason"] == "runtime_cap_reached"

    def test_cost_cap_reached(self, worker_base_state):
        state = dict(worker_base_state)
        state["max_cost_usd"] = 1.0
        state["estimated_cost_usd"] = 1.5
        assert _route_after_worker(state) == "stopped"
        assert state["stop_reason"] == "cost_cap_reached"

    def test_caps_not_reached(self, worker_base_state):
        """When caps are set but not exceeded, should check tasks instead."""
        state = dict(worker_base_state)
        state["max_runtime_minutes"] = 60
        state["started_at"] = time.time() - 30  # 30 seconds ago
        state["max_cost_usd"] = 5.0
        state["estimated_cost_usd"] = 2.0
        # No tasks -> all pending is empty -> "complete"
        assert _route_after_worker(state) == "complete"


# ── _route_after_worker: Task-based Routing Tests ──────────────────────────

class TestRouteAfterWorkerTaskRouting:
    def test_all_tasks_complete(self, worker_base_state):
        state = dict(worker_base_state)
        state["tasks"] = [
            _make_task("t1", "complete"),
            _make_task("t2", "complete"),
        ]
        assert _route_after_worker(state) == "complete"
        assert state.get("stop_reason") is None

    def test_some_pending_some_ready(self, worker_base_state):
        """Should return 'loop' when pending tasks exist and at least one is ready."""
        state = dict(worker_base_state)
        state["tasks"] = [
            _make_task("t1", "complete"),
            _make_task("t2", "pending", depends_on=["t1"]),
            _make_task("t3", "pending", depends_on=["t1"]),
        ]
        assert _route_after_worker(state) == "loop"
        assert state.get("stop_reason") is None

    def test_pending_with_ready_dependencies(self, worker_base_state):
        """A pending task whose dependencies are complete -> ready -> loop."""
        state = dict(worker_base_state)
        state["tasks"] = [
            _make_task("t1", "complete"),
            _make_task("t2", "pending", depends_on=["t1"]),
        ]
        assert _route_after_worker(state) == "loop"

    def test_deadlock_detected(self, worker_base_state):
        """All pending tasks have incomplete dependencies -> deadlock."""
        state = dict(worker_base_state)
        state["tasks"] = [
            _make_task("t1", "pending", depends_on=["t2"]),
            _make_task("t2", "pending", depends_on=["t3"]),
            _make_task("t3", "pending", depends_on=["t1"]),
        ]
        assert _route_after_worker(state) == "stopped"
        assert state["stop_reason"] == "dependency_deadlock"

    def test_empty_tasks(self, worker_base_state):
        """No tasks at all -> all pending is empty -> complete."""
        state = dict(worker_base_state)
        assert _route_after_worker(state) == "complete"
        assert state.get("stop_reason") is None

    def test_all_tasks_pending_no_deps(self, worker_base_state):
        """All pending with no dependencies -> all are ready -> loop."""
        state = dict(worker_base_state)
        state["tasks"] = [
            _make_task("t1", "pending"),
            _make_task("t2", "pending"),
        ]
        assert _route_after_worker(state) == "loop"

    def test_mixed_statuses_with_deadlock(self, worker_base_state):
        """Some complete, some pending, but no ready tasks -> deadlock."""
        state = dict(worker_base_state)
        state["tasks"] = [
            _make_task("t1", "complete"),
            _make_task("t2", "pending", depends_on=["t3"]),
            _make_task("t3", "pending", depends_on=["t2"]),
        ]
        assert _route_after_worker(state) == "stopped"
        assert state["stop_reason"] == "dependency_deadlock"


# ── _route_after_worker: Stop Reason + Tasks Interaction ───────────────────

class TestRouteAfterWorkerStopAndTasks:
    def test_stop_reason_trumps_tasks(self, worker_base_state):
        """If stop reason is triggered, return 'stopped' regardless of tasks."""
        state = dict(worker_base_state)
        state["interrupted"] = True
        state["tasks"] = [
            _make_task("t1", "complete"),
            _make_task("t2", "running"),
        ]
        assert _route_after_worker(state) == "stopped"
        assert state["stop_reason"] == "user_interrupt"

    def test_interrupt_signal_object(self, worker_base_state):
        """Interrupt signal via Event-like object."""
        state = dict(worker_base_state)
        mock_event = type("MockEvent", (), {"is_set": lambda self: True})()
        state["interrupt_signal"] = mock_event
        assert _route_after_worker(state) == "stopped"
        assert state["stop_reason"] == "user_interrupt"

    def test_interrupt_signal_not_set(self, worker_base_state):
        """Interrupt signal exists but not set -> should not stop."""
        state = dict(worker_base_state)
        mock_event = type("MockEvent", (), {"is_set": lambda self: False})()
        state["interrupt_signal"] = mock_event
        # No tasks -> complete
        assert _route_after_worker(state) == "complete"
        assert state.get("stop_reason") is None


# ── _route_after_critic: Stop Reason Tests ─────────────────────────────────

class TestRouteAfterCriticStopReasons:
    def test_user_interrupt(self, critic_base_state):
        state = dict(critic_base_state)
        state["interrupted"] = True
        assert _route_after_critic(state) == "stopped"
        assert state["stop_reason"] == "user_interrupt"

    def test_runtime_cap(self, critic_base_state):
        state = dict(critic_base_state)
        state["max_runtime_minutes"] = 1
        state["started_at"] = time.time() - 120
        assert _route_after_critic(state) == "stopped"
        assert state["stop_reason"] == "runtime_cap_reached"

    def test_cost_cap(self, critic_base_state):
        state = dict(critic_base_state)
        state["max_cost_usd"] = 1.0
        state["estimated_cost_usd"] = 1.5
        assert _route_after_critic(state) == "stopped"
        assert state["stop_reason"] == "cost_cap_reached"


# ── _route_after_critic: Autonomy Mode Routing Tests ───────────────────────

class TestRouteAfterCriticAutonomyMode:
    """Test how autonomy_mode affects critic routing when confidence is low."""

    @pytest.mark.parametrize("mode", ["autonomous", "hybrid", "guided", "full"])
    def test_low_confidence_non_interactive_modes_go_to_replan(self, critic_base_state, mode):
        """Non-interactive modes should route to 'replan' when confidence is low."""
        state = dict(critic_base_state)
        state["autonomy_mode"] = mode
        state["section_confidence"] = {"section1": 0.2}
        state["iteration_index"] = 0
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "replan"
        assert state.get("stop_reason") is None

    def test_low_confidence_interactive_mode_awaits_user(self, critic_base_state):
        """Interactive mode should route to 'await_user_critic' when confidence is low."""
        state = dict(critic_base_state)
        state["autonomy_mode"] = "interactive"
        state["section_confidence"] = {"section1": 0.2}
        state["iteration_index"] = 0
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "await_user_critic"
        assert state.get("stop_reason") is None

    def test_high_confidence_goes_to_combiner(self, critic_base_state):
        """Regardless of autonomy mode, high confidence goes to combiner."""
        state = dict(critic_base_state)
        state["autonomy_mode"] = "interactive"
        state["section_confidence"] = {"section1": 0.9}
        state["iteration_index"] = 0
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "combiner"

    def test_all_modes_high_confidence(self, critic_base_state):
        """All autonomy modes route to combiner with high confidence."""
        for mode in ["autonomous", "hybrid", "guided", "interactive", "full"]:
            state = dict(critic_base_state)
            state["autonomy_mode"] = mode
            state["section_confidence"] = {"t1": 0.85, "t2": 0.92}
            state["iteration_index"] = 0
            state["max_iterations"] = 4
            assert _route_after_critic(state) == "combiner", f"Failed for mode={mode}"

    @pytest.mark.parametrize("mode", ["autonomous", "hybrid", "guided", "interactive", "full"])
    def test_max_iterations_all_modes(self, critic_base_state, mode):
        """All modes go to combiner when max iterations reached, even with low confidence."""
        state = dict(critic_base_state)
        state["autonomy_mode"] = mode
        state["section_confidence"] = {"t1": 0.1}
        state["iteration_index"] = 4
        state["max_iterations"] = 4
        result = _route_after_critic(state)
        assert result == "combiner", f"Failed for mode={mode}"
        assert state["stop_reason"] == "max_iterations_reached"

    def test_missing_autonomy_mode_defaults_to_replan(self, critic_base_state):
        """When autonomy_mode is missing, should default to replan (not interactive)."""
        state = dict(critic_base_state)
        del state["autonomy_mode"]
        state["section_confidence"] = {"t1": 0.15}
        state["iteration_index"] = 0
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "replan"


# ── _route_after_critic: Confidence and Iteration Boundary Tests ──────────

class TestRouteAfterCriticBoundaries:
    def test_confidence_at_threshold(self, critic_base_state):
        """Confidence exactly at 0.35 is NOT low (>= 0.35 is acceptable)."""
        state = dict(critic_base_state)
        state["section_confidence"] = {"t1": 0.35}
        state["iteration_index"] = 0
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "combiner"

    def test_confidence_just_below_threshold(self, critic_base_state):
        """Confidence just below 0.35 IS low."""
        state = dict(critic_base_state)
        state["section_confidence"] = {"t1": 0.349}
        state["iteration_index"] = 0
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "replan"

    def test_all_zero_confidence(self, critic_base_state):
        """All zero confidence -> low -> replan (in non-interactive mode)."""
        state = dict(critic_base_state)
        state["section_confidence"] = {"t1": 0.0, "t2": 0.0}
        state["autonomy_mode"] = "autonomous"
        state["iteration_index"] = 0
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "replan"

    def test_empty_confidence_dict(self, critic_base_state):
        """Empty confidence dict: no low scores found -> combiner."""
        state = dict(critic_base_state)
        state["section_confidence"] = {}
        state["iteration_index"] = 0
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "combiner"

    def test_max_iterations_exactly_not_reached(self, critic_base_state):
        """When iteration < max_iter -> still allowed to replan."""
        state = dict(critic_base_state)
        state["section_confidence"] = {"t1": 0.1}
        state["iteration_index"] = 3
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "replan"

    def test_max_iterations_at_limit(self, critic_base_state):
        """When iteration == max_iter -> must go to combiner."""
        state = dict(critic_base_state)
        state["section_confidence"] = {"t1": 0.1}
        state["iteration_index"] = 4
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "combiner"
        assert state["stop_reason"] == "max_iterations_reached"

    def test_max_iterations_zero(self, critic_base_state):
        """When max_iterations is 0, iteration_index 0 should still check >=."""
        state = dict(critic_base_state)
        state["section_confidence"] = {"t1": 0.1}
        state["max_iterations"] = 0
        state["iteration_index"] = 0
        result = _route_after_critic(state)
        assert result == "combiner", f"Expected combiner, got {result}"
        assert "max_iterations_reached" in str(state.get("run_warnings", []))

    def test_mixed_confidence_one_low(self, critic_base_state):
        """If any section has low confidence, trigger replan/await."""
        state = dict(critic_base_state)
        state["section_confidence"] = {"t1": 0.9, "t2": 0.95, "t3": 0.2}
        state["autonomy_mode"] = "autonomous"
        state["iteration_index"] = 0
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "replan"

    def test_mixed_confidence_all_high(self, critic_base_state):
        """All sections have high confidence -> combiner."""
        state = dict(critic_base_state)
        state["section_confidence"] = {"t1": 0.8, "t2": 0.75, "t3": 0.9}
        state["iteration_index"] = 0
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "combiner"


# ── _route_after_critic: Run Warnings Tests ────────────────────────────────

class TestRouteAfterCriticWarnings:
    def test_max_iterations_appends_warning(self, critic_base_state):
        """When max iterations reached with low confidence, a warning is logged."""
        state = dict(critic_base_state)
        state["section_confidence"] = {"t1": 0.1}
        state["iteration_index"] = 4
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "combiner"
        assert len(state["run_warnings"]) == 1
        assert "critic:max_iterations_reached" in state["run_warnings"][0]

    def test_no_warning_when_high_confidence(self, critic_base_state):
        """High confidence at max iterations should NOT log a warning."""
        state = dict(critic_base_state)
        state["section_confidence"] = {"t1": 0.9}
        state["iteration_index"] = 4
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "combiner"
        # High confidence -> the low_confidence check is false, so no warning
        assert len(state["run_warnings"]) == 0

    def test_multiple_low_confidence_sections_one_warning(self, critic_base_state):
        """Multiple low-confidence sections should only append one warning at max iter."""
        state = dict(critic_base_state)
        state["section_confidence"] = {"t1": 0.1, "t2": 0.2, "t3": 0.05}
        state["iteration_index"] = 4
        state["max_iterations"] = 4
        assert _route_after_critic(state) == "combiner"
        assert len(state["run_warnings"]) == 1


def test_graph_structure():
    """Smoke test: build_graph() should compile without errors."""
    graph = build_graph()
    assert graph is not None
