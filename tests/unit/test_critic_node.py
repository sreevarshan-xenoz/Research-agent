from __future__ import annotations

from research_agent.orchestration.nodes.critic import critic_node


def test_critic_applies_metadata_fallback_penalty() -> None:
    state = {
        "run_id": "run-critic",
        "topic": "topic",
        "template": "ieee",
        "phase": "workers_complete",
        "iteration_index": 0,
        "max_iterations": 3,
        "depth": "balanced",
        "autonomy_mode": "hybrid",
        "max_runtime_minutes": 25,
        "max_cost_usd": 5.0,
        "estimated_cost_usd": 0.0,
        "started_at": 0.0,
        "interrupt_signal": None,
        "stop_reason": None,
        "tasks": [
            {
                "task_id": "t1",
                "title": "Task 1",
                "objective": "Obj 1",
                "depends_on": [],
                "status": "complete",
            }
        ],
        "section_confidence": {},
        "clarification_questions": [],
        "needs_clarification": False,
        "task_findings": {
            "t1": {
                "arxiv": {
                    "item_count": 2,
                    "metadata_only_count": 2,
                    "warning_count": 0,
                    "warnings": [],
                    "items": [
                        {"title": "A", "snippet": ""},
                        {"title": "B", "snippet": ""},
                    ],
                }
            }
        },
        "critic_notes": [],
        "combined_sections": [],
        "citations": [],
        "latex_main": "",
        "bibtex": "",
        "artifact_root": "artifacts",
        "artifact_dir": "",
        "run_warnings": [],
    }

    result = critic_node(state)

    # Base confidence with 2 items would be 0.25; metadata penalty should not increase it.
    assert result["section_confidence"]["t1"] <= 0.25
    assert any("Metadata fallback penalty applied for t1" in note for note in result["critic_notes"])
