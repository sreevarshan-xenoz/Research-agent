from __future__ import annotations

import random

from research_agent.orchestration.state import GraphState
from research_agent.templates import get_template

# Last-resort fallback when user has no past research history
_FALLBACK_TRENDING_TOPICS = [
    "Large Language Model Reasoning Capabilities",
    "Autonomous Agent Architectures",
    "Retrieval-Augmented Generation Optimization",
    "Vision-Language Model Alignment",
    "Efficient Fine-Tuning Methods",
    "AI Safety and Alignment Research",
    "Scientific Discovery with AI",
    "Causal Machine Learning",
]


def _is_ambiguous_topic(topic: str) -> bool:
    # If the topic already contains clarification context, do not flag it as ambiguous again.
    if "Clarification context:" in topic:
        return False
        
    normalized = topic.strip().lower()
    if len(normalized.split()) <= 4:
        return True

    broad_markers = {
        "ai",
        "machine learning",
        "research",
        "technology",
        "future",
        "innovation",
    }
    return any(marker in normalized for marker in broad_markers)


def _get_candidate_topics(state: GraphState) -> list[str]:
    """Get candidate topics for auto-selection, prioritizing past user research.

    Order of priority:
    1. User's past research topics (from session history / agent memory)
    2. Hardcoded fallback trending topics (last resort)
    """
    past_topics = state.get("past_research_topics", [])
    if past_topics:
        return past_topics
    return list(_FALLBACK_TRENDING_TOPICS)


def _auto_select_topic(state: GraphState) -> str | None:
    """If the topic is empty or a signal for auto-discover, return a trending topic
    sourced from the user's past research history.

    Returns None if the topic should be used as-is (not auto-selected).
    """
    topic = state.get("topic", "")
    normalized = topic.strip().lower()
    # Empty topic, placeholder, or explicit auto-discover signal
    if not normalized or normalized in ("", "auto-discover", "auto_discover", "auto"):
        candidates = _get_candidate_topics(state)
        return random.choice(candidates) if candidates else None
    return None


async def intake_node(state: GraphState) -> dict:
    normalized_topic = state["topic"].strip()
    run_warnings: list[str] = list(state.get("run_warnings", []))
    
    # P39: Load research template for context-sensitive intake
    template_id = state.get("research_template", "standard")
    tmpl = get_template(template_id)
    
    # Autonomous mode with empty/placeholder topic → auto-select from past research
    is_autonomous = state.get("autonomy_mode", "") == "autonomous"
    auto_topic = _auto_select_topic(state) if is_autonomous else None
    
    if auto_topic is not None:
        normalized_topic = auto_topic
        run_warnings.append(f"intake:auto_selected_topic:{auto_topic}")
    
    needs_clarification = _is_ambiguous_topic(normalized_topic)
    
    # P39: If template has built-in clarification prompts, always ask them
    if tmpl and tmpl.clarification_prompts and not is_autonomous:
        needs_clarification = True
    
    # In autonomous mode, auto-selected topics are never ambiguous
    if is_autonomous and auto_topic is not None:
        needs_clarification = False
    
    # P39: Merge template clarification prompts with default questions
    clarification_questions = list(state.get("clarification_questions", []))
    if tmpl and tmpl.clarification_prompts and needs_clarification:
        for prompt in tmpl.clarification_prompts:
            if prompt not in clarification_questions:
                clarification_questions.append(prompt)
    
    return {
        "topic": normalized_topic,
        "phase": "intake_complete",
        "needs_clarification": needs_clarification,
        "clarification_questions": clarification_questions,
        "run_warnings": run_warnings,
    }
