from __future__ import annotations

from research_agent.orchestration.state import GraphState


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


async def intake_node(state: GraphState) -> dict:
    normalized_topic = state["topic"].strip()
    needs_clarification = _is_ambiguous_topic(normalized_topic)
    return {
        "topic": normalized_topic,
        "phase": "intake_complete",
        "needs_clarification": needs_clarification,
    }
