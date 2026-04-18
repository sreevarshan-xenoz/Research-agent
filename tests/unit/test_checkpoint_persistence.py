from __future__ import annotations

from pathlib import Path

from research_agent.observability.checkpoints import append_run_event, load_latest_checkpoint, save_checkpoint
from research_agent.orchestration.state import SubtopicTask, WorkflowState


def test_save_and_load_latest_checkpoint(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("CHECKPOINT_ROOT", str(tmp_path / "checkpoints"))

    state = WorkflowState(
        run_id="run-checkpoint",
        topic="Checkpoint topic",
        tasks=[SubtopicTask(task_id="t1", title="Task", objective="Obj", status="complete")],
        phase="workers_complete",
    )

    save_checkpoint(state, label="phase_a")
    state.phase = "completed"
    state.stop_reason = "completed"
    save_checkpoint(state, label="phase_b")

    restored = load_latest_checkpoint("run-checkpoint")
    assert restored is not None
    assert restored.phase == "completed"
    assert restored.stop_reason == "completed"
    assert restored.tasks[0].task_id == "t1"


def test_append_run_event_writes_ndjson(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RUN_EVENT_ROOT", str(tmp_path / "events"))

    event_path = append_run_event(
        run_id="run-events",
        event="status",
        payload={"message": "ok", "value": 1},
    )

    assert event_path.exists()
    content = event_path.read_text(encoding="utf-8").strip()
    assert '"event": "status"' in content
    assert '"message": "ok"' in content
