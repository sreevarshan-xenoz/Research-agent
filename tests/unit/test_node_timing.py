"""Tests for NodeTimer wrapping, timing accumulation, and diagnostics integration."""

from __future__ import annotations

from typing import Generator
import pytest

from research_agent.observability.logging import (
    NodeTimer,
    get_node_timings,
    record_node_timing,
    reset_node_timings,
    wrap_node_fn,
)


@pytest.fixture(autouse=True)
def _clean_timings() -> Generator[None, None, None]:
    """Reset accumulated timings before and after each test."""
    reset_node_timings()
    yield
    reset_node_timings()


# ---------------------------------------------------------------------------
# NodeTimer context manager
# ---------------------------------------------------------------------------


def test_nodetimer_records_duration() -> None:
    """NodeTimer should set duration_ms after exiting the block."""
    with NodeTimer("test_node") as timer:
        pass  # no-op — should still record ~0ms
    assert timer.duration_ms >= 0
    assert timer.node_name == "test_node"


def test_nodetimer_duration_is_positive_ms() -> None:
    """NodeTimer should record a positive duration for actual work."""
    with NodeTimer("test_slow") as timer:
        _busy_wait(0.01)
    assert timer.duration_ms >= 5, f"Expected >=5ms, got {timer.duration_ms:.2f}ms"


def _busy_wait(seconds: float) -> None:
    import time
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        pass


# ---------------------------------------------------------------------------
# record_node_timing / get_node_timings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_node_timing_single() -> None:
    await record_node_timing("alpha", 10.5)
    stats = get_node_timings()
    assert "alpha" in stats
    assert stats["alpha"]["count"] == 1
    assert stats["alpha"]["total_ms"] == 10.5


@pytest.mark.asyncio
async def test_record_node_timing_multiple_calls() -> None:
    for _ in range(5):
        await record_node_timing("beta", 100.0)
    stats = get_node_timings()
    assert stats["beta"]["count"] == 5
    assert stats["beta"]["total_ms"] == 500.0
    assert stats["beta"]["avg_ms"] == 100.0
    assert stats["beta"]["max_ms"] == 100.0


@pytest.mark.asyncio
async def test_record_node_timing_multiple_nodes() -> None:
    await record_node_timing("x", 5.0)
    await record_node_timing("y", 15.0)
    await record_node_timing("x", 10.0)
    stats = get_node_timings()
    assert stats["x"]["count"] == 2
    assert stats["x"]["total_ms"] == 15.0
    assert stats["y"]["count"] == 1
    assert stats["y"]["total_ms"] == 15.0


def test_get_node_timings_empty() -> None:
    stats = get_node_timings()
    assert stats == {}


# ---------------------------------------------------------------------------
# reset_node_timings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_clears_all_timings() -> None:
    await record_node_timing("z", 42.0)
    assert len(get_node_timings()) == 1
    reset_node_timings()
    assert get_node_timings() == {}


# ---------------------------------------------------------------------------
# wrap_node_fn (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wrap_node_fn_preserves_return_value() -> None:
    async def sample_node(state: dict) -> dict:
        return {"phase": "done", "result": state.get("value", 0) * 2}

    wrapped = wrap_node_fn("sample", sample_node)
    result = await wrapped({"run_id": "test-1", "value": 21})
    assert result["phase"] == "done"
    assert result["result"] == 42


@pytest.mark.asyncio
async def test_wrap_node_fn_records_timing() -> None:
    async def slow_node(state: dict) -> dict:
        # Use a CPU-bound busy-wait to guarantee measurable wall time
        _busy_wait(0.015)
        return {"phase": "done"}

    wrapped = wrap_node_fn("slow", slow_node)
    await wrapped({"run_id": "test-2"})

    stats = get_node_timings()
    assert "slow" in stats
    assert stats["slow"]["count"] == 1
    assert stats["slow"]["total_ms"] >= 1  # at least 1ms of real wall time


@pytest.mark.asyncio
async def test_wrap_node_fn_preserves_metadata() -> None:
    async def my_custom_node(state: dict) -> dict:
        """My custom docstring."""
        return {"phase": "done"}

    wrapped = wrap_node_fn("custom", my_custom_node)
    assert wrapped.__name__ == my_custom_node.__name__
    assert wrapped.__qualname__ == my_custom_node.__qualname__
    assert "My custom docstring" in (wrapped.__doc__ or "")


@pytest.mark.asyncio
async def test_wrap_node_fn_captures_error_timing() -> None:
    """Even when the node raises, timing should still be recorded."""

    async def failing_node(state: dict) -> dict:
        msg = "boom"
        raise ValueError(msg)

    wrapped = wrap_node_fn("failing", failing_node)
    with pytest.raises(ValueError, match="boom"):
        await wrapped({"run_id": "test-3"})

    stats = get_node_timings()
    assert "failing" in stats
    assert stats["failing"]["count"] == 1


@pytest.mark.asyncio
async def test_wrap_node_fn_multiple_calls_accumulate() -> None:
    async def quick_node(state: dict) -> dict:
        return {"phase": "done"}

    wrapped = wrap_node_fn("quick", quick_node)
    for _ in range(5):
        await wrapped({"run_id": "test-4"})

    stats = get_node_timings()
    assert stats["quick"]["count"] == 5


# ---------------------------------------------------------------------------
# wrap_node_fn (sync)
# ---------------------------------------------------------------------------


def test_wrap_node_fn_sync_preserves_return() -> None:
    def sync_node(state: dict) -> dict:
        return {"phase": "sync_done", "value": state.get("x", 0) + 1}

    wrapped = wrap_node_fn("sync_node", sync_node)
    result = wrapped({"run_id": "sync-1", "x": 99})
    assert result["phase"] == "sync_done"
    assert result["value"] == 100


def test_wrap_node_fn_sync_records_timing() -> None:
    def slow_sync(state: dict) -> dict:
        _busy_wait(0.01)
        return {"phase": "done"}

    wrapped = wrap_node_fn("slow_sync", slow_sync)
    wrapped({"run_id": "sync-2"})

    stats = get_node_timings()
    assert "slow_sync" in stats
    assert stats["slow_sync"]["count"] == 1
    assert stats["slow_sync"]["total_ms"] >= 5


# ---------------------------------------------------------------------------
# Diagnostics integration (via get_memory_diagnostics)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_diagnostics_includes_node_timings() -> None:
    """Verify get_memory_diagnostics() returns node_timings key."""
    from research_agent.orchestration.graph import get_memory_diagnostics

    await record_node_timing("alpha", 10.0)
    await record_node_timing("beta", 20.0)

    diagnostics: dict[str, object] = await get_memory_diagnostics()
    assert "node_timings" in diagnostics
    assert isinstance(diagnostics["node_timings"], dict)
    assert "alpha" in diagnostics["node_timings"]  # type: ignore[operator]
    assert "beta" in diagnostics["node_timings"]  # type: ignore[operator]


@pytest.mark.asyncio
async def test_diagnostics_node_timings_values() -> None:
    from research_agent.orchestration.graph import get_memory_diagnostics

    await record_node_timing("gamma", 100.0)
    await record_node_timing("gamma", 200.0)

    diagnostics: dict[str, object] = await get_memory_diagnostics()
    timings = diagnostics["node_timings"]
    assert isinstance(timings, dict)
    g: dict[str, object] = timings["gamma"]  # type: ignore[index]
    assert g["count"] == 2
    assert g["total_ms"] == 300.0
    assert g["avg_ms"] == 150.0
    assert g["max_ms"] == 200.0
