from __future__ import annotations

from research_agent.orchestration.nodes.indexing import get_contradiction_links, indexing_node


def test_indexing_detects_contradiction_links() -> None:
    state = {
        "run_id": "run-contradiction",
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
        "tasks": [],
        "section_confidence": {},
        "clarification_questions": [],
        "needs_clarification": False,
        "task_findings": {
            "t1": {
                "web": {
                    "item_count": 1,
                    "warning_count": 0,
                    "warnings": [],
                    "items": [
                        {
                            "title": "Study A",
                            "snippet": "Method improves benchmark accuracy and supports better performance.",
                            "url": "https://example.com/a",
                        }
                    ],
                }
            },
            "t2": {
                "web": {
                    "item_count": 1,
                    "warning_count": 0,
                    "warnings": [],
                    "items": [
                        {
                            "title": "Study B",
                            "snippet": "Method fails benchmark accuracy and is not better performance.",
                            "url": "https://example.com/b",
                        }
                    ],
                }
            },
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

    result = indexing_node(state)
    links = get_contradiction_links("run-contradiction")

    assert links
    assert any(w.startswith("indexing:contradiction_links:") for w in result["run_warnings"])
