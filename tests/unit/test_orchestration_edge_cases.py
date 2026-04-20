from __future__ import annotations

import time

import pytest

from research_agent.orchestration.graph import _stop_reason
from research_agent.orchestration.nodes.worker import (
    get_pending_task_ids,
    get_ready_task_ids,
)


class TestStopReason:
    def test_no_stop_when_no_caps(self) -> None:
        state: dict = {
            "started_at": time.time(),
            "max_runtime_minutes": 0,
            "max_cost_usd": 0.0,
            "estimated_cost_usd": 0.0,
        }
        assert _stop_reason(state) is None

    def test_runtime_cap_not_reached_under_limit(self) -> None:
        state: dict = {
            "started_at": time.time(),
            "max_runtime_minutes": 30,
            "max_cost_usd": 0.0,
            "estimated_cost_usd": 0.0,
        }
        result = _stop_reason(state)
        assert result is None

    def test_runtime_cap_reached_over_limit(self) -> None:
        state: dict = {
            "started_at": time.time() - 1800,
            "max_runtime_minutes": 25,
            "max_cost_usd": 0.0,
            "estimated_cost_usd": 0.0,
        }
        assert _stop_reason(state) == "runtime_cap_reached"

    def test_cost_cap_reached(self) -> None:
        state: dict = {
            "started_at": time.time(),
            "max_runtime_minutes": 0,
            "max_cost_usd": 5.0,
            "estimated_cost_usd": 5.0,
        }
        assert _stop_reason(state) == "cost_cap_reached"

    def test_user_interrupt(self) -> None:
        class MockEvent:
            def is_set(self) -> bool:
                return True

        state: dict = {
            "interrupt_signal": MockEvent(),
            "started_at": time.time(),
            "max_runtime_minutes": 0,
            "max_cost_usd": 0.0,
            "estimated_cost_usd": 0.0,
        }
        assert _stop_reason(state) == "user_interrupt"


class TestDependencyResolution:
    def test_get_ready_task_ids_pending_with_deps_complete(self) -> None:
        tasks = [
            {"task_id": "t1", "status": "pending", "depends_on": []},
            {"task_id": "t2", "status": "pending", "depends_on": ["t1"]},
        ]
        ready = get_ready_task_ids(tasks)
        assert "t1" in ready
        assert "t2" not in ready

    def test_get_ready_task_ids_blocked_missing_dep(self) -> None:
        tasks = [
            {"task_id": "t1", "status": "pending", "depends_on": []},
            {"task_id": "t2", "status": "pending", "depends_on": ["t1"]},
        ]
        ready = get_ready_task_ids(tasks)
        assert "t1" in ready
        assert "t2" not in ready

    def test_get_ready_task_ids_partial_complete(self) -> None:
        tasks = [
            {"task_id": "t1", "status": "complete", "depends_on": []},
            {"task_id": "t2", "status": "pending", "depends_on": ["t1"]},
            {"task_id": "t3", "status": "pending", "depends_on": ["t2"]},
        ]
        ready = get_ready_task_ids(tasks)
        assert "t2" in ready
        assert "t3" not in ready

    def test_get_pending_task_ids(self) -> None:
        tasks = [
            {"task_id": "t1", "status": "pending"},
            {"task_id": "t2", "status": "complete"},
            {"task_id": "t3", "status": "pending"},
        ]
        pending = get_pending_task_ids(tasks)
        assert "t1" in pending
        assert "t3" in pending
        assert "t2" not in pending

    def test_empty_tasks(self) -> None:
        tasks: list = []
        assert get_ready_task_ids(tasks) == []
        assert get_pending_task_ids(tasks) == []


class TestEmptySectionConfidence:
    def test_empty_confidence_dict(self) -> None:
        section_confidence: dict = {}
        if section_confidence:
            avg = sum(section_confidence.values()) / len(section_confidence)
        else:
            avg = 0.0
        assert avg == 0.0

    def test_partial_confidence_dict(self) -> None:
        section_confidence = {"t1": 0.8, "t2": 0.0}
        avg = sum(section_confidence.values()) / len(section_confidence)
        assert avg == 0.4