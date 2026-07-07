"""P26 — Advanced AI Research Assistant: Research Suggestions Router.

Provides autonomous research topic suggestions by mining:
- Past session topics from the session store
- Agent memory (last topics per user)
- Watchdog literature monitoring topics
- Default trend-aware suggestions

Registered as a router in webapp.py.
"""

from __future__ import annotations

from pathlib import Path
import json
import logging

from fastapi import APIRouter, Depends
from research_agent.app.auth import User, current_active_user
from research_agent.chat.memory import get_memory_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research_suggestions"])

_TRENDING_TOPICS = [
    {"title": "Large Language Model Reasoning Capabilities", "domain": "NLP", "reason": "Trending — major advances in chain-of-thought and tool-use"},
    {"title": "Autonomous Agent Architectures", "domain": "AI", "reason": "Hot topic — multi-agent systems and agentic workflows"},
    {"title": "Retrieval-Augmented Generation (RAG) Optimization", "domain": "NLP/IR", "reason": "Active area — chunking, routing, and hybrid search"},
    {"title": "Vision-Language Model Alignment", "domain": "Multimodal", "reason": "Rapid progress — instruction tuning for vision-language models"},
    {"title": "Efficient Fine-Tuning Methods", "domain": "Efficiency", "reason": "Practical — LoRA, QLoRA, and parameter-efficient transfer"},
    {"title": "AI Safety and Alignment Research", "domain": "Safety", "reason": "Critical — red teaming, interpretability, and value alignment"},
    {"title": "Scientific Discovery with AI", "domain": "Science", "reason": "Emerging — AlphaFold, GNoME, and AI-driven materials discovery"},
    {"title": "Causal Machine Learning", "domain": "ML Theory", "reason": "Growing — causal inference, treatment effects, and counterfactuals"},
]


def _load_sessions() -> dict:
    """Load session data from the session store."""
    session_path = Path(".runtime/sessions.json")
    if not session_path.exists():
        return {}
    try:
        return json.loads(session_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_past_topics_for_user(user_id: str) -> list[str]:
    """Load past research topics for a specific user from session history and agent memory.

    Mines:
    - Past session topics from the session store
    - Agent memory (last topics per session for this user)

    Returns a deduplicated list of topic strings, most recent first.
    """
    seen: set[str] = set()
    topics: list[str] = []

    # 1. Mine past session topics
    sessions = _load_sessions()
    for sid, session in sessions.items():
        if isinstance(session, dict):
            sess_user = session.get("user_id", "")
            topic = session.get("original_topic", "")
            if sess_user == user_id and topic and len(topic) > 5 and topic not in seen:
                seen.add(topic)
                topics.append(topic)

    # 2. Mine agent memory for last topics
    try:
        agent_memory = get_memory_store()
        if hasattr(agent_memory, "_sessions"):
            for sid, mem in list(agent_memory._sessions.items()):  # type: ignore[union-attr]
                if hasattr(mem, "last_topic") and mem.last_topic:
                    topic = mem.last_topic
                    if topic not in seen and len(topic) > 5:
                        seen.add(topic)
                        topics.append(topic)
    except Exception:
        pass

    return topics


def _load_watchdog_topics() -> list[str]:
    """Load watchdog monitor topics from watchdog state."""
    watchdog_path = Path(".runtime/watchdog_state.json")
    if not watchdog_path.exists():
        return []
    try:
        data = json.loads(watchdog_path.read_text(encoding="utf-8"))
        profiles = data.get("profiles", {})
        topics = []
        for profile in profiles.values():
            if isinstance(profile, dict) and profile.get("enabled", False):
                query = profile.get("query", "")
                if query:
                    topics.append(query)
        return topics
    except Exception:
        return []


@router.get("/suggestions")
async def get_research_suggestions(
    user: User = Depends(current_active_user)
):
    """Get autonomous research topic suggestions for the user.

    Mines past session topics, agent memory, watchdog monitoring topics,
    and trending research areas to suggest the most relevant next research topics.
    """
    user_id = str(user.id)
    suggestions = []

    # 1. Mine past session topics
    sessions = _load_sessions()
    past_topics = set()
    for sid, session in sessions.items():
        if isinstance(session, dict):
            sess_user = session.get("user_id", "")
            topic = session.get("original_topic", "")
            if sess_user == user_id and topic and len(topic) > 5:
                past_topics.add(topic)

    for topic in list(past_topics)[:5]:
        suggestions.append({
            "title": f"Deep dive: {topic[:60]}",
            "domain": "past_research",
            "reason": "Continue your previous research",
            "query": topic,
            "type": "past_topic",
        })

    # 2. Mine agent memory for last topics
    try:
        agent_memory = get_memory_store()
        # Get all sessions from memory (iterate through internal dict)
        if hasattr(agent_memory, "_sessions"):
            for sid, mem in list(agent_memory._sessions.items()):  # type: ignore[union-attr]
                if hasattr(mem, "last_topic") and mem.last_topic:
                    topic = mem.last_topic
                    if topic not in past_topics and len(topic) > 5:
                        suggestions.append({
                            "title": f"Research: {topic[:60]}",
                            "domain": "agent_memory",
                            "reason": "From your agent conversations",
                            "query": topic,
                            "type": "memory_topic",
                        })
    except Exception:
        pass

    # 3. Mine watchdog monitoring topics
    watchdog_topics = _load_watchdog_topics()
    for wt in watchdog_topics[:3]:
        suggestions.append({
            "title": f"Monitor: {wt[:60]}",
            "domain": "literature_monitoring",
            "reason": "Active watchdog monitor topic",
            "query": wt,
            "type": "watchdog_topic",
        })

    # 4. Add trending topics (if we have fewer than 6 suggestions)
    if len(suggestions) < 6:
        for tt in _TRENDING_TOPICS:
            tt_query = tt["title"]
            # Avoid duplicates with past topics
            if not any(tt_query.lower() in s.get("query", "").lower() for s in suggestions):
                suggestions.append({
                    "title": tt["title"],
                    "domain": tt["domain"],
                    "reason": tt["reason"],
                    "query": tt["title"],
                    "type": "trending",
                })
                if len(suggestions) >= 8:
                    break

    return {
        "suggestions": suggestions,
        "total": len(suggestions),
        "has_past_research": len(past_topics) > 0,
    }
