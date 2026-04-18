from __future__ import annotations

from research_agent.orchestration.nodes.citation_verifier import citation_verifier_node


def _base_state() -> dict:
    return {
        "run_id": "run-cv",
        "topic": "Topic",
        "template": "ieee",
        "phase": "combined",
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
                "title": "Supported",
                "objective": "Has evidence",
                "depends_on": [],
                "status": "complete",
            },
            {
                "task_id": "t2",
                "title": "Unsupported",
                "objective": "No evidence",
                "depends_on": [],
                "status": "complete",
            },
        ],
        "section_confidence": {"t1": 0.8, "t2": 0.1},
        "clarification_questions": [],
        "needs_clarification": False,
        "task_findings": {
            "t1": {
                "fake": {
                    "item_count": 1,
                    "warning_count": 0,
                    "warnings": [],
                    "items": [
                        {
                            "title": "Evidence 1",
                            "url": "https://example.com/e1",
                            "year": "2026",
                            "authors": ["Author A"],
                        }
                    ],
                }
            },
            "t2": {
                "fake": {
                    "item_count": 0,
                    "warning_count": 0,
                    "warnings": [],
                    "items": [],
                }
            },
        },
        "critic_notes": [],
        "combined_sections": [
            {
                "task_id": "t1",
                "heading": "Supported section",
                "content": "Evidence (Deep RAG): useful content.",
            },
            {
                "task_id": "t2",
                "heading": "Unsupported section",
                "content": "Evidence (Deep RAG):\nNo specific evidence chunks found.",
            },
        ],
        "citations": [],
        "latex_main": "",
        "bibtex": "",
        "artifact_root": "artifacts",
        "artifact_dir": "",
        "run_warnings": [],
    }


def test_citation_verifier_rejects_unsupported_sections() -> None:
    state = _base_state()

    result = citation_verifier_node(state)

    assert len(result["combined_sections"]) == 1
    assert result["combined_sections"][0]["task_id"] == "t1"
    assert result["citations"]
    assert all(c["key"].startswith("t1_") for c in result["citations"])
    assert any(
        warning.startswith("citation_verifier:unsupported_section_claims:t2")
        for warning in result["run_warnings"]
    )


def test_citation_verifier_keeps_supported_sections() -> None:
    state = _base_state()
    state["task_findings"]["t2"]["fake"]["item_count"] = 1
    state["task_findings"]["t2"]["fake"]["items"] = [
        {
            "title": "Evidence 2",
            "url": "https://example.com/e2",
            "year": "2026",
            "authors": ["Author B"],
        }
    ]
    state["combined_sections"][1]["content"] = "Evidence (Deep RAG): supported text."

    result = citation_verifier_node(state)

    assert len(result["combined_sections"]) == 2
    assert any(c["key"].startswith("t2_") for c in result["citations"])
    assert not any(
        warning.startswith("citation_verifier:unsupported_section_claims")
        for warning in result["run_warnings"]
    )
