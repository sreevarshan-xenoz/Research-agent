"""Concurrency stress test: spawn 5 concurrent run_graph() calls and verify session isolation.

Each concurrent run uses a unique run_id and empty tool registry.
The test verifies that:
- All 5 calls complete without exception
- Each result has the correct run_id (no cross-contamination)
- Shared global caches are cleaned up properly (cleanup_run_state in finally block)
- No deadlocks from asyncio.Lock contention
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


# ---------------------------------------------------------------------------
# Cache cleanup is handled by conftest.py's clean_global_caches (synchronous,
# autouse), which prevents asyncio.run() conflicts with pytest-asyncio on
# Windows. No per-file autouse fixture needed here.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_run_graph_session_isolation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """5 concurrent run_graph() calls should each complete with isolated state.

    This exercises concurrent access to:
    - Shared global caches (_INDEX_CACHE, _CONTRADICTION_CACHE, _INDEXED_TASKS_CACHE)
    - asyncio.Lock contention across multiple coroutines
    - cleanup_run_state() called concurrently from finally blocks
    """
    # ------------------------------------------------------------------
    # Monkeypatch async functions so the graph can complete.
    # ------------------------------------------------------------------
    async def _mock_get_contradiction_links(run_id: str) -> list:
        return []

    monkeypatch.setattr(
        "research_agent.orchestration.nodes.critic.get_contradiction_links",
        _mock_get_contradiction_links,
    )
    monkeypatch.setattr(
        "research_agent.orchestration.nodes.combiner.get_contradiction_links",
        _mock_get_contradiction_links,
    )
    # get_or_create_index is now awaited in combiner.py — use an async factory
    # that returns a mock with async asearch.
    mock_index = AsyncMock()
    mock_index.asearch.return_value = []

    async def _mock_get_or_create_index(run_id: str) -> AsyncMock:
        return mock_index

    monkeypatch.setattr(
        "research_agent.orchestration.nodes.combiner.get_or_create_index",
        _mock_get_or_create_index,
    )

    # ------------------------------------------------------------------
    # Build 5 independent WorkflowState objects with unique run IDs.
    # Each gets its own artifact subdirectory under tmp_path.
    # ------------------------------------------------------------------
    # Use a single unambiguous topic for all 5 runs (>4 words, no broad markers)
    # to avoid the clarifier path and ensure deterministic behavior.
    topic = "Comparative analysis of retrieval augmentation for coding agents"

    states = [
        WorkflowState(
            run_id=f"stress-{i}",
            topic=topic,
            artifact_root=str(tmp_path / f"run-{i}"),
            max_iterations=1,
        )
        for i in range(5)
    ]

    # ------------------------------------------------------------------
    # Fire all 5 concurrent run_graph() calls via asyncio.gather.
    # return_exceptions=True allows all tasks to complete even if some fail.
    # ------------------------------------------------------------------
    import asyncio

    results = await asyncio.gather(
        *(run_graph(state, registry={}) for state in states),
        return_exceptions=True,
    )

    # Separate into exceptions and successful results
    exceptions: list[tuple[int, BaseException]] = [
        (i, r) for i, r in enumerate(results) if isinstance(r, BaseException)
    ]
    successes: list[tuple[int, WorkflowState]] = [
        (i, r) for i, r in enumerate(results) if not isinstance(r, BaseException)
    ]

    # --- ASSERTION 1: No concurrent call should raise an exception ----------
    assert not exceptions, (
        f"{len(exceptions)} concurrent run_graph() calls raised exceptions:\n"
        + "\n".join(f"  run-{i}: {exc!r}" for i, exc in exceptions)
    )

    # --- ASSERTION 2: All 5 calls completed successfully --------------------
    assert len(successes) == 5, f"Expected 5 successes, got {len(successes)}"

    # --- ASSERTION 3: Each result has the correct run_id (no cross-talk) ----
    for orig_idx, result in successes:
        expected_run_id = f"stress-{orig_idx}"
        assert result.run_id == expected_run_id, (
            f"run-{orig_idx}: expected run_id={expected_run_id!r}, "
            f"got {result.run_id!r}"
        )

    # --- ASSERTION 4: Each call reached completion --------------------------
    for orig_idx, result in successes:
        assert result.phase == "completed", (
            f"run-{orig_idx}: expected phase='completed', got {result.phase!r}, "
            f"stop_reason={result.stop_reason!r}, "
            f"topic={result.topic!r}"
        )
        assert result.stop_reason == "completed", (
            f"run-{orig_idx}: expected stop_reason='completed', "
            f"got {result.stop_reason!r}"
        )

    # --- ASSERTION 5: Each run produced its own artifact directory ----------
    for orig_idx, result in successes:
        assert result.artifact_dir, (
            f"run-{orig_idx}: artifact_dir is empty"
        )
        artifact_path = Path(result.artifact_dir)
        assert artifact_path.exists(), (
            f"run-{orig_idx}: artifact dir {result.artifact_dir} does not exist"
        )
        assert (artifact_path / "summary.json").exists(), (
            f"run-{orig_idx}: summary.json not found in {result.artifact_dir}"
        )

    # --- ASSERTION 6: All tasks completed in every run ----------------------
    for orig_idx, result in successes:
        assert len(result.tasks) > 0, (
            f"run-{orig_idx}: no tasks were planned"
        )
        assert all(
            task.status == "complete" for task in result.tasks
        ), (
            f"run-{orig_idx}: not all tasks completed — "
            f"statuses: {[t.status for t in result.tasks]}"
        )

    # --- ASSERTION 7: Shared global caches are empty after cleanup ----------
    # cleanup_run_state() is called in each run_graph() finally block,
    # which should purge all per-run state from the global caches.
    from research_agent.orchestration.nodes.indexing import (
        _CONTRADICTION_CACHE,
        _INDEX_CACHE,
        _INDEXED_TASKS_CACHE,
    )

    assert len(_INDEX_CACHE) == 0, (
        f"INDEX_CACHE should be empty after cleanup, "
        f"got {len(_INDEX_CACHE)} entries: {list(_INDEX_CACHE.keys())}"
    )
    assert len(_CONTRADICTION_CACHE) == 0, (
        f"CONTRADICTION_CACHE should be empty after cleanup, "
        f"got {len(_CONTRADICTION_CACHE)} entries"
    )
    assert len(_INDEXED_TASKS_CACHE) == 0, (
        f"INDEXED_TASKS_CACHE should be empty after cleanup, "
        f"got {len(_INDEXED_TASKS_CACHE)} entries"
    )


@pytest.mark.asyncio
async def test_concurrent_run_graph_graceful_partial_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When one run fails, the other concurrent runs should still complete.

    This verifies that an exception in one concurrent run_graph() call
    does not cascade to the other calls (i.e., the asyncio event loop
    and shared locks are not left in a corrupted state).
    """
    async def _mock_get_contradiction_links(run_id: str) -> list:
        return []

    monkeypatch.setattr(
        "research_agent.orchestration.nodes.critic.get_contradiction_links",
        _mock_get_contradiction_links,
    )
    monkeypatch.setattr(
        "research_agent.orchestration.nodes.combiner.get_contradiction_links",
        _mock_get_contradiction_links,
    )
    mock_index = AsyncMock()
    mock_index.asearch.return_value = []

    async def _mock_get_or_create_index(run_id: str) -> AsyncMock:
        return mock_index

    monkeypatch.setattr(
        "research_agent.orchestration.nodes.combiner.get_or_create_index",
        _mock_get_or_create_index,
    )

    import asyncio

    # One failing task and 4 normal tasks
    async def failing_run() -> WorkflowState:
        msg = "simulated catastrophic failure"
        raise RuntimeError(msg)

    # Use a single unambiguous topic for all normal runs
    topic = "Efficient transformer architectures for long document summarization"
    normal_states = [
        WorkflowState(
            run_id=f"partial-{i}",
            topic=topic,
            artifact_root=str(tmp_path / f"partial-{i}"),
            max_iterations=1,
        )
        for i in range(4)
    ]

    # Mix the failing task with normal tasks
    coros: list = [failing_run()] + [run_graph(s, registry={}) for s in normal_states]

    results = await asyncio.gather(*coros, return_exceptions=True)

    # First call should have failed
    assert isinstance(results[0], BaseException), (
        f"Expected RuntimeError, got {type(results[0])}"
    )

    # Remaining 4 should have succeeded
    succeeded = [r for r in results[1:] if not isinstance(r, BaseException)]
    assert len(succeeded) == 4, (
        f"Expected 4 successful runs, got {len(succeeded)}"
    )

    for result in succeeded:
        assert result.phase == "completed"
        assert result.stop_reason == "completed"


@pytest.mark.asyncio
async def test_concurrent_run_graph_context_isolation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """10 concurrent run_graph() calls must each have isolated trace context.

    This test verifies:
    - Each concurrent run sees its own run_id as the active trace context
      during node execution (no cross-contamination)
    - After all 10 runs complete, the trace context is restored to its
      pre-run value (empty)
    - If an outer context is set, it is preserved after all runs complete
    - No exceptions from concurrent context var access
    """
    from research_agent.observability.logging import (
        get_current_trace_id,
        set_trace_context,
    )

    # ------------------------------------------------------------------
    # Monkeypatch async functions so the graph can complete.
    # ------------------------------------------------------------------
    async def _mock_get_contradiction_links(run_id: str) -> list:
        return []

    monkeypatch.setattr(
        "research_agent.orchestration.nodes.critic.get_contradiction_links",
        _mock_get_contradiction_links,
    )
    monkeypatch.setattr(
        "research_agent.orchestration.nodes.combiner.get_contradiction_links",
        _mock_get_contradiction_links,
    )
    mock_index = AsyncMock()
    mock_index.asearch.return_value = []

    async def _mock_get_or_create_index(run_id: str) -> AsyncMock:
        return mock_index

    monkeypatch.setattr(
        "research_agent.orchestration.nodes.combiner.get_or_create_index",
        _mock_get_or_create_index,
    )

    # ------------------------------------------------------------------
    # Hook into intake_node to capture the active trace_id inside each run.
    # ------------------------------------------------------------------
    captured_per_run: dict[str, str] = {}  # run_id -> trace_id seen inside node

    async def _tracing_intake_node(state: dict) -> dict:
        # Capture the active trace context inside the graph execution
        trace_id_seen = get_current_trace_id()
        captured_per_run[state["run_id"]] = trace_id_seen
        return {"phase": "intake_done"}

    monkeypatch.setattr(
        "research_agent.orchestration.graph.intake_node",
        _tracing_intake_node,
    )
    # Also patch the wrapped version used inside build_graph
    monkeypatch.setattr(
        "research_agent.orchestration.graph.wrap_node_fn",
        lambda name, fn: fn,  # bypass NodeTimer wrapping for simplicity
    )

    # ------------------------------------------------------------------
    # Build 10 independent WorkflowState objects with unique run IDs.
    # ------------------------------------------------------------------
    topic = "Concurrent context isolation test for trace propagation"

    states = [
        WorkflowState(
            run_id=f"ctx-concurrent-{i:02d}",
            topic=topic,
            artifact_root=str(tmp_path / f"ctx-run-{i}"),
            max_iterations=1,
        )
        for i in range(10)
    ]
    expected_run_ids = [s.run_id for s in states]

    # ------------------------------------------------------------------
    # Fire all 10 concurrent run_graph() calls.
    # ------------------------------------------------------------------
    import asyncio

    results = await asyncio.gather(
        *(run_graph(state, registry={}) for state in states),
        return_exceptions=True,
    )

    # Separate into exceptions and successful results
    exceptions: list[tuple[int, BaseException]] = [
        (i, r) for i, r in enumerate(results) if isinstance(r, BaseException)
    ]
    successes: list[tuple[int, WorkflowState]] = [
        (i, r) for i, r in enumerate(results) if not isinstance(r, BaseException)
    ]

    # --- ASSERTION 1: No concurrent call should raise an exception ----------
    assert not exceptions, (
        f"{len(exceptions)} concurrent run_graph() calls raised exceptions:\n"
        + "\n".join(f"  run-{i}: {exc!r}" for i, exc in exceptions)
    )

    # --- ASSERTION 2: All 10 calls completed -------------------------------
    assert len(successes) == 10, (
        f"Expected 10 successes, got {len(successes)}"
    )

    # --- ASSERTION 3: Each run completed successfully -----------------------
    for orig_idx, result in successes:
        assert result.phase == "completed", (
            f"run-{orig_idx}: expected phase='completed', got {result.phase!r}"
        )
        assert result.stop_reason == "completed"

    # --- ASSERTION 4: Context isolation — each run saw its own run_id -------
    for orig_idx, result in successes:
        rid = result.run_id
        assert rid in captured_per_run, (
            f"run-{orig_idx}: run_id={rid!r} not found in captured_per_run. "
            f"captured keys: {list(captured_per_run.keys())}"
        )
        assert captured_per_run[rid] == rid, (
            f"run-{orig_idx}: expected trace context inside node to be "
            f"{rid!r}, got {captured_per_run[rid]!r}"
        )

    # --- ASSERTION 5: Every expected run_id was captured (no missing runs) --
    for rid in expected_run_ids:
        assert rid in captured_per_run, (
            f"Missing trace capture for expected run_id {rid!r}. "
            f"Captured: {list(captured_per_run.keys())}"
        )

    # --- ASSERTION 6: No unexpected run_ids were captured -------------------
    for rid in captured_per_run:
        assert rid in expected_run_ids, (
            f"Unexpected run_id {rid!r} appeared in trace captures. "
            f"Expected: {expected_run_ids}"
        )

    # --- ASSERTION 7: Context restored to empty after all runs complete -----
    current = get_current_trace_id()
    assert current == "", (
        f"Expected empty context after all 10 concurrent runs, got {current!r}"
    )

    # --- ASSERTION 8: Outer context is preserved if set ---------------------
    outer_token = set_trace_context("outer-persistent-context")
    assert get_current_trace_id() == "outer-persistent-context"

    # Run a single graph inside the outer context
    single_state = WorkflowState(
        run_id="ctx-outer-test",
        topic=topic,
        artifact_root=str(tmp_path / "ctx-outer-test"),
        max_iterations=1,
    )
    await run_graph(single_state, registry={})

    # Outer context still intact
    assert get_current_trace_id() == "outer-persistent-context", (
        f"Expected outer context preserved, got {get_current_trace_id()!r}"
    )

    # Run 10 concurrent calls again while outer context is set
    states2 = [
        WorkflowState(
            run_id=f"ctx-outer-concurrent-{i:02d}",
            topic=topic,
            artifact_root=str(tmp_path / f"ctx-outer-run-{i}"),
            max_iterations=1,
        )
        for i in range(10)
    ]
    results2 = await asyncio.gather(
        *(run_graph(state, registry={}) for state in states2),
        return_exceptions=True,
    )

    # No exceptions with outer context
    exceptions2 = [
        (i, r) for i, r in enumerate(results2) if isinstance(r, BaseException)
    ]
    assert not exceptions2, (
        f"{len(exceptions2)} concurrent runs raised with outer context:\n"
        + "\n".join(f"  run-{i}: {exc!r}" for i, exc in exceptions2)
    )

    # Outer context preserved after all concurrent runs complete
    assert get_current_trace_id() == "outer-persistent-context", (
        f"Expected outer context preserved after 10 concurrent runs, "
        f"got {get_current_trace_id()!r}"
    )

    # Clean up outer token
    from research_agent.observability.logging import _trace_id_var as _var
    _var.reset(outer_token)
    assert get_current_trace_id() == ""
