from __future__ import annotations

import re
from research_agent.models import agenerate_json
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


def _extract_topic_keywords(topic: str) -> list[str]:
    """Extract key noun phrases from topic for adaptive fallback tasks."""
    # Simple extraction: find capitalized words and common research terms
    words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", topic)
    if not words:
        # Fallback to all words >= 4 chars
        words = re.findall(r"\b[a-zA-Z]{4,}\b", topic.lower())
    return words[:5]  # Top 5 keywords


def _build_adaptive_fallback_tasks(topic: str) -> list[dict]:
    """Build topic-adaptive fallback tasks when LLM fails."""
    keywords = _extract_topic_keywords(topic)
    if len(keywords) >= 2:
        kw1, kw2 = keywords[0], keywords[1]
    else:
        kw1, kw2 = "topic", "research"

    return [
        {
            "task_id": "t1",
            "title": f"Background on {kw1}",
            "objective": f"Research background, definitions, and context for: {topic}",
            "depends_on": [],
            "status": "pending",
            "providers": ["duckduckgo"],
        },
        {
            "task_id": "t2",
            "title": f"{kw2} research papers",
            "objective": f"Find academic papers and publications about: {topic}",
            "depends_on": [],
            "status": "pending",
            "providers": ["arxiv", "semantic_scholar", "openalex"],
        },
        {
            "task_id": "t3",
            "title": "Methods analysis",
            "objective": f"Analyze methodologies and approaches in: {topic}",
            "depends_on": ["t2"],
            "status": "pending",
            "providers": ["semantic_scholar", "openalex"],
        },
        {
            "task_id": "t4",
            "title": "Synthesis and findings",
            "objective": f"Compile key findings and prepare for sections: {topic}",
            "depends_on": ["t1", "t3"],
            "status": "pending",
            "providers": ["duckduckgo", "arxiv"],
        },
    ]


async def planner_node(state: GraphState) -> dict:
    topic = state["topic"]
    await apublish_progress(
        agent="Planner",
        status="running",
        detail="Building task graph",
        message="Planning research subtasks",
    )

    # Topic-adaptive fallback tasks (used when head model unavailable or fails)
    tasks = _build_adaptive_fallback_tasks(topic)

    # Use depth to determine task count
    depth = state.get("depth", "balanced")
    task_counts = {"quick": 3, "balanced": 4, "deep": 6}
    num_tasks = task_counts.get(depth, 4)

    prompt = (
        f"Decompose the following research topic into {num_tasks} specific sub-research tasks: '{topic}'.\n"
        f"Depth: {depth} (quick=3, balanced=4, deep=6 tasks).\n"
        "Each task must have a 'task_id' (e.g. t1, t2), 'title', 'objective', 'depends_on' (a list of other task_ids), "
        "and 'providers' (a list of recommended providers from: duckduckgo, arxiv, semantic_scholar, openalex).\n"
        "Ensure the tasks form a valid Directed Acyclic Graph (DAG).\n"
        "Return a JSON object with a 'tasks' key containing the list of task objects."
    )

    # Use the HEAD model (local Ollama) for task planning
    llm_plan = await agenerate_json(role="head", prompt=prompt)
    if llm_plan and isinstance(llm_plan, dict) and "tasks" in llm_plan:
        raw_tasks = llm_plan["tasks"]
        valid_tasks = []
        for t in raw_tasks:
            if isinstance(t, dict) and all(k in t for k in ("task_id", "title", "objective")):
                t["status"] = "pending"
                t["depends_on"] = t.get("depends_on", [])
                t["providers"] = t.get("providers", [])
                if not isinstance(t["depends_on"], list):
                    t["depends_on"] = []
                if not isinstance(t["providers"], list):
                    t["providers"] = []
                valid_tasks.append(t)
        if valid_tasks:
            tasks = valid_tasks

    await apublish_progress(
        agent="Planner",
        status="complete",
        detail=f"Planned {len(tasks)} tasks",
        message="Task graph ready",
    )
    return {"tasks": tasks, "phase": "planned"}
