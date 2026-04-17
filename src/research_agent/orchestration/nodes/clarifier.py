from __future__ import annotations

from research_agent.orchestration.state import GraphState


def clarifier_node(state: GraphState) -> dict:
    if not state["needs_clarification"]:
        return {"clarification_questions": [], "phase": "clarified"}

    questions = [
        "What exact scope should this research focus on?",
        "What depth do you want: overview, implementation detail, or publication-depth?",
        "Do you want the emphasis on methods, benchmarks, or real-world applications?",
    ]
    return {
        "clarification_questions": questions,
        "phase": "clarification_needed",
    }


def awaiting_user_node(state: GraphState) -> dict:
    return {
        "phase": "awaiting_user_clarification",
        "stop_reason": "clarification_required",
    }
