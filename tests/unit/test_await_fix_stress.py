"""Stress test: critic_node + combiner_node with real get_contradiction_links / get_or_create_index.

Verifies the ``await`` fix in critic.py and combiner.py works end-to-end:

- ``critic_node`` calls ``await get_contradiction_links(run_id)`` — the fix
  ensures it gets a list, not a coroutine object.
- ``combiner_node`` calls both ``await get_or_create_index(run_id)`` and
  ``await get_contradiction_links(run_id)`` — both were missing ``await``.

The existing unit tests mock these functions, so they never exercise the
actual async call. This test calls the real functions by:

1. Running ``indexing_node`` to populate ``_CONTRADICTION_CACHE`` with
   real contradiction links.
2. Calling ``critic_node`` — verifies it receives contradiction data.
3. Calling ``combiner_node`` — verifies it gets a real ``ResearchIndex``
   (in-memory Qdrant) and contradiction links.
4. Repeating steps 1-3 across multiple concurrent run_ids.
"""

from __future__ import annotations

import asyncio
from typing import Any, Generator

import pytest

from research_agent.orchestration.nodes import critic_node, combiner_node, indexing_node
from research_agent.orchestration.nodes.indexing import (
    _CONTRADICTION_CACHE,
    _CONTRADICTION_CACHE_LOCK,
    _INDEX_CACHE,
    _INDEXED_TASKS_CACHE,
    _INDEXED_TASKS_CACHE_LOCK,
    cleanup_run_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_full_state(
    run_id: str,
    *,
    tasks: list[dict[str, str | list[str]]] | None = None,
    findings: dict[str, dict[str, dict[str, Any]]] | None = None,
    iteration_index: int = 0,
    max_iterations: int = 3,
) -> dict[str, Any]:
    """Build a ``GraphState``-compatible dict with sensible defaults.

    The returned dict matches the ``GraphState`` TypedDict schema and
    can be passed directly to ``critic_node`` / ``combiner_node`` /
    ``indexing_node``.
    """
    default_tasks = tasks or [
        {"task_id": "t1", "title": "Task 1", "objective": "Obj 1", "depends_on": [], "status": "complete"},
        {"task_id": "t2", "title": "Task 2", "objective": "Obj 2", "depends_on": [], "status": "complete"},
    ]
    default_findings = findings or {
        "t1": {
            "web": {
                "item_count": 1,
                "warning_count": 0,
                "metadata_only_count": 0,
                "warnings": [],
                "items": [
                    {
                        "title": "Study A",
                        "snippet": "Method improves benchmark accuracy and supports better performance.",
                        "url": f"https://example.com/a/{run_id}",
                    }
                ],
            }
        },
        "t2": {
            "web": {
                "item_count": 1,
                "warning_count": 0,
                "metadata_only_count": 0,
                "warnings": [],
                "items": [
                    {
                        "title": "Study B",
                        "snippet": "Method fails benchmark accuracy and is not better performance.",
                        "url": f"https://example.com/b/{run_id}",
                    }
                ],
            }
        },
    }

    return {
        "run_id": run_id,
        "topic": "Test topic for await fix stress test",
        "template": "ieee",
        "language": "en",
        "phase": "indexed",
        "iteration_index": iteration_index,
        "max_iterations": max_iterations,
        "depth": "balanced",
        "autonomy_mode": "hybrid",
        "max_runtime_minutes": 25,
        "max_cost_usd": 5.0,
        "estimated_cost_usd": 0.0,
        "started_at": 0.0,
        "interrupted": False,
        "stop_reason": None,
        "tasks": default_tasks,
        "section_confidence": {},
        "clarification_questions": [],
        "needs_clarification": False,
        "task_findings": default_findings,
        "critic_notes": [],
        "critic_user_feedback": None,
        "combined_sections": [],
        "citations": [],
        "figures": [],
        "latex_main": "",
        "bibtex": "",
        "presentation_tex": None,
        "poster_tex": None,
        "future_research_agenda": None,
        "comparison_table": None,
        "guard_report": None,
        "math_verification_report": None,
        "peer_review_report": None,
        "knowledge_graph": None,
        "bias_report": None,
        "artifact_root": "/tmp/await-fix-test",
        "artifact_dir": "",
        "acm_layout": None,
        "run_warnings": [],
    }


async def _clean_all_caches() -> None:
    """Purge all per-run state from the three global caches."""
    async with _CONTRADICTION_CACHE_LOCK:
        _CONTRADICTION_CACHE.clear()
    # _INDEX_CACHE entries need to have their Qdrant clients closed
    # before removal to prevent connection leaks.
    for run_id in list(_INDEX_CACHE.keys()):
        await cleanup_run_state(run_id)
    async with _INDEXED_TASKS_CACHE_LOCK:
        _INDEXED_TASKS_CACHE.clear()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def _clean_caches() -> Generator[None, None, None]:
    """Ensure clean global caches before each test that requests it."""
    asyncio.run(_clean_all_caches())
    yield
    asyncio.run(_clean_all_caches())


# ---------------------------------------------------------------------------
# Test: single-run critic_node with real get_contradiction_links
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_critic_node_real_contradiction_links(_clean_caches: None) -> None:
    """critic_node should receive real contradiction links from the index.

    Flow:
      1. Run indexing_node to populate ``_CONTRADICTION_CACHE`` with
         contradiction links derived from the findings.
      2. Call critic_node with the same run_id — it internally calls
         ``await get_contradiction_links(run_id)``.
      3. Verify the critic detected the contradiction (penalty applied).
    """
    run_id = "await-fix-critic-real"

    # Step 1: index — this creates contradiction links internally
    state = _make_full_state(run_id)
    idx_result = await indexing_node(state)
    assert "contradiction_links" in str(idx_result["run_warnings"]), (
        "Expected contradiction warnings from indexing_node"
    )

    # Step 2: run critic with real get_contradiction_links
    critic_result = await critic_node(state)

    # Step 3: verify critic saw the contradictions
    notes = critic_result["critic_notes"]
    assert any("Contradiction penalty" in note for note in notes), (
        f"Expected contradiction penalty note in critic output, got notes: {notes}"
    )
    # With 1 item per task, base confidence = max(0.0, min(1.0, 1/8 - 0 - 0 - penalty))
    # penalty = min(0.2, 1 * 0.05) = 0.05
    # So confidence = 1/8 - 0.05 = 0.125 - 0.05 = 0.075
    scores = critic_result["section_confidence"]
    assert scores.get("t1", 1.0) <= 0.2, (
        f"Expected low confidence due to contradiction penalty, got t1={scores.get('t1')}"
    )


# ---------------------------------------------------------------------------
# Test: single-run combiner_node with real index and contradiction links
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_combiner_node_real_index_and_contradictions(_clean_caches: None) -> None:
    """combiner_node should use a real ResearchIndex and real contradiction links.

    Flow:
      1. Run indexing_node to populate both ``_INDEX_CACHE`` (via
         ``get_or_create_index``) and ``_CONTRADICTION_CACHE``.
      2. Call combiner_node — it internally calls
         ``await get_or_create_index(run_id)`` and
         ``await get_contradiction_links(run_id)``.
      3. Verify sections were produced (meaning the index worked) and
         contradiction context was included.
    """
    run_id = "await-fix-combiner-real"

    # Step 1: index — creates the ResearchIndex and contradiction cache
    state = _make_full_state(run_id)
    await indexing_node(state)

    # Step 2: run combiner with real get_or_create_index + get_contradiction_links
    # Note: combiner internally calls agenerate_text which needs an LLM.
    # If the LLM isn't available, it falls back to crude synthesis.
    combiner_result = await combiner_node(state)

    # Step 3: verify output
    sections = combiner_result.get("combined_sections", [])
    assert len(sections) > 0, (
        f"Expected at least 1 combined section, got {len(sections)}"
    )
    for section in sections:
        assert "content" in section, (
            f"Section {section.get('task_id')} missing 'content'"
        )
        assert "citation_map" in section, (
            f"Section {section.get('task_id')} missing 'citation_map'"
        )
        raw = section.get("raw_evidence", "")
        assert "REF1" in raw or "contradiction" in raw.lower(), (
            f"Expected reference or contradiction context in raw evidence, "
            f"got: {raw[:200]}..."
        )


# ---------------------------------------------------------------------------
# Test: single run — critic_node + combiner_node in sequence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_critic_then_combiner_sequence_with_real_calls(_clean_caches: None) -> None:
    """Full sequence: index -> critic -> combiner, all with real async functions."""
    run_id = "await-fix-full-seq"

    state = _make_full_state(run_id)
    await indexing_node(state)

    # Critic — exercises await get_contradiction_links
    critic_result = await critic_node(state)
    assert "section_confidence" in critic_result

    # Combiner — exercises await get_or_create_index + await get_contradiction_links
    combiner_result = await combiner_node(state)
    assert len(combiner_result["combined_sections"]) > 0


# ---------------------------------------------------------------------------
# Stress: concurrent runs — each with its own run_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_critic_and_combiner_with_real_calls(_clean_caches: None) -> None:
    """5 concurrent workflows, each with real get_contradiction_links /
    get_or_create_index, to stress-test async lock contention.

    Each workflow:
      1. indexing_node (populates caches)
      2. critic_node (reads from _CONTRADICTION_CACHE)
      3. combiner_node (reads from both caches + creates index)

    Verifies:
      - No ``TypeError: 'coroutine' object is not iterable``
      - All results are valid
      - Global caches have correct entries after all workflows
    """
    async def _run_workflow(run_id: str) -> dict[str, Any]:
        """Run index -> critic -> combiner with real functions."""
        state = _make_full_state(run_id)
        await indexing_node(state)
        critic_out = await critic_node(state)
        combiner_out = await combiner_node(state)
        return {
            "run_id": run_id,
            "critic_scores": critic_out.get("section_confidence", {}),
            "critic_notes": critic_out.get("critic_notes", []),
            "sections_count": len(combiner_out.get("combined_sections", [])),
        }

    num_workflows = 5
    run_ids = [f"await-fix-concurrent-{i}" for i in range(num_workflows)]

    results = await asyncio.gather(
        *(_run_workflow(rid) for rid in run_ids),
        return_exceptions=True,
    )

    # --- ASSERTION 1: No exception raised (await fix works!) ----------------
    exceptions = [(i, r) for i, r in enumerate(results) if isinstance(r, BaseException)]
    assert not exceptions, (
        f"{len(exceptions)} concurrent workflow(s) raised exceptions:\n"
        + "\n".join(f"  {run_ids[i]}: {exc!r}" for i, exc in exceptions)
    )

    # --- ASSERTION 2: Each run returned valid critic output -----------------
    successes = [r for r in results if not isinstance(r, BaseException)]
    for outcome in successes:
        assert len(outcome["critic_scores"]) > 0, (
            f"Run {outcome['run_id']}: critic produced no scores"
        )
        assert any("Contradiction" in note for note in outcome["critic_notes"]), (
            f"Run {outcome['run_id']}: expected contradiction note in critic output,\n"
            f"got notes: {outcome['critic_notes']}"
        )

    # --- ASSERTION 3: Each run produced sections via combiner ----------------
    for outcome in successes:
        assert outcome["sections_count"] > 0, (
            f"Run {outcome['run_id']}: combiner produced 0 sections"
        )

    # --- ASSERTION 4: Caches match expected run_ids -------------------------
    async with _CONTRADICTION_CACHE_LOCK:
        cached_runs = set(_CONTRADICTION_CACHE.keys())
    expected_runs = set(run_ids)
    assert cached_runs == expected_runs, (
        f"CONTRADICTION_CACHE has unexpected keys: "
        f"{cached_runs - expected_runs}"
    )

    indexed_runs = set(_INDEX_CACHE.keys())
    assert indexed_runs == expected_runs, (
        f"INDEX_CACHE has unexpected keys: "
        f"{indexed_runs - expected_runs}"
    )


# ---------------------------------------------------------------------------
# Stress: concurrent critic_node calls with shared contradiction cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_critic_only_same_run_id(_clean_caches: None) -> None:
    """8 concurrent critic_node calls sharing the same run_id and
    contradiction cache, to verify lock safety.

    If the ``await get_contradiction_links`` fix were broken, this would
    raise ``TypeError: 'coroutine' object is not iterable`` or produce
    corrupted data due to lock contention on ``_CONTRADICTION_CACHE_LOCK``.
    """
    run_id = "await-fix-critic-concurrent-same"

    # Populate the cache once via indexing_node
    state = _make_full_state(run_id)
    await indexing_node(state)

    # Launch 8 concurrent critic calls
    num_concurrent = 8
    results = await asyncio.gather(
        *(critic_node(state) for _ in range(num_concurrent)),
        return_exceptions=True,
    )

    exceptions = [(i, r) for i, r in enumerate(results) if isinstance(r, BaseException)]
    assert not exceptions, (
        f"{len(exceptions)} concurrent critic_node calls raised exceptions:\n"
        + "\n".join(f"  call-{i}: {exc!r}" for i, exc in exceptions)
    )

    # All results should have identical scores (same input)
    scores_list = [r["section_confidence"] for r in results if not isinstance(r, BaseException)]
    first_scores = scores_list[0]
    for i, scores in enumerate(scores_list[1:], start=1):
        assert scores == first_scores, (
            f"Concurrent critic call {i}: scores differ from first call: "
            f"{scores} vs {first_scores}"
        )


# ---------------------------------------------------------------------------
# Stress: concurrent combiner_node calls with shared index
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_combiner_only_same_run_id(_clean_caches: None) -> None:
    """4 concurrent combiner_node calls sharing the same run_id and
    ResearchIndex, to verify lock safety.

    If the ``await get_or_create_index`` fix were broken, this would raise
    ``TypeError: 'coroutine' object is not iterable``.
    """
    run_id = "await-fix-combiner-concurrent-same"

    # Populate the index and contradiction cache once
    state = _make_full_state(run_id)
    await indexing_node(state)

    # Launch 4 concurrent combiner calls
    num_concurrent = 4
    results = await asyncio.gather(
        *(combiner_node(state) for _ in range(num_concurrent)),
        return_exceptions=True,
    )

    exceptions = [(i, r) for i, r in enumerate(results) if isinstance(r, BaseException)]
    assert not exceptions, (
        f"{len(exceptions)} concurrent combiner_node calls raised exceptions:\n"
        + "\n".join(f"  call-{i}: {exc!r}" for i, exc in exceptions)
    )

    # All results should have sections
    for i, r in enumerate(results):
        if not isinstance(r, BaseException):
            assert len(r.get("combined_sections", [])) > 0, (
                f"Concurrent combiner call {i}: no sections produced"
            )
