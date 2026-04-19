from __future__ import annotations

from research_agent.models import generate_json
from research_agent.observability import publish_progress
from research_agent.orchestration.state import GraphState


def clarifier_node(state: GraphState) -> dict:
    if not state["needs_clarification"]:
        return {"clarification_questions": [], "phase": "clarified"}

    topic = state["topic"]
    publish_progress(
        agent="Clarifier",
        status="running",
        detail="Generating clarification questions",
        message="Analyzing topic ambiguity",
    )

    # Fallback questions used when the head model is unavailable or fails
    questions = [
        "What exact scope should this research focus on?",
        "What depth do you want: overview, implementation detail, or publication-depth?",
        "Do you want the emphasis on methods, benchmarks, or real-world applications?",
    ]

    prompt = (
        f"The user wants to research the topic: '{topic}'.\n"
        "This topic is broad or ambiguous. Generate 2-4 targeted clarification questions "
        "to help narrow down the research scope, depth, and domain.\n"
        "Return a JSON object with a 'questions' key containing a list of strings."
    )

    # Use the HEAD model (local Ollama) for orchestration tasks
    llm_questions = generate_json(role="head", prompt=prompt)
    if llm_questions and isinstance(llm_questions, dict) and "questions" in llm_questions:
        raw_questions = llm_questions["questions"]
        if isinstance(raw_questions, list) and len(raw_questions) >= 2:
            questions = [str(q) for q in raw_questions if isinstance(q, str) and q.strip()]
            if len(questions) < 2:
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
    publish_progress(
        agent="Clarifier",
        status="waiting",
        detail="Awaiting user scope details",
        message="Need clarification before research",
    )
    return {
        "phase": "awaiting_user_clarification",
        "stop_reason": "clarification_required",
    }
