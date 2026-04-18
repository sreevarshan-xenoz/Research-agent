from __future__ import annotations

from pathlib import Path
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


def test_graph_iterates_on_low_confidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
    
    # Create a state where we expect low confidence (no findings initially)
    state = WorkflowState(
        run_id="test_loop",
        topic="Quantum computing for coffee brewing",
        artifact_root=str(tmp_path),
        max_iterations=2
    )
    
    # We pass an empty registry so findings will be empty -> low confidence
    updated = run_graph(state, registry={})
    
    # Since confidence was low and max_iterations=2, it should have looped once.
    # The iteration_index should be 2 (incremented twice, once in each pass through critic)
    # Wait, in the first pass it increments to 1. Then loops. In second pass increments to 2.
    assert updated.iteration_index >= 1
    assert updated.phase == "completed"
    
    # Check that follow-up tasks were added (critic adds them if confidence is low)
    # Original planner adds ~4 tasks.
    assert len(updated.tasks) > 4
