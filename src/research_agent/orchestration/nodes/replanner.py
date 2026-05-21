from __future__ import annotations

import json
from research_agent.models import agenerate_json
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState, GraphTask


async def replanner_node(state: GraphState) -> dict:
    """Dynamically updates the research tasks based on current findings and critic notes."""
    await apublish_progress(
        agent="Replanner",
        status="running",
        detail="Adjusting research roadmap",
        message="Evaluating if new subtopics are needed",
    )
    
    findings = state.get("task_findings", {})
    critic_notes = state.get("critic_notes", [])
    if not findings or not critic_notes:
        return {"phase": "replanner_skipped"}

    # Summarize findings and critic notes
    current_tasks = [t["title"] for t in state["tasks"]]
    
    prompt = (
        "You are a research director. Based on the following findings and critic feedback, "
        "decide if any new research tasks (subtopics) should be added to the roadmap.\n\n"
        f"Topic: {state['topic']}\n"
        f"Current Tasks: {', '.join(current_tasks)}\n"
        f"Critic Feedback: {' '.join(critic_notes)}\n\n"
        "Instructions:\n"
        "1. If a significant new subtopic is needed, describe it.\n"
        "2. Output exactly a JSON list of new tasks: [{'title': '...', 'objective': '...', 'depends_on': []}].\n"
        "3. If no new tasks are needed, return an empty list [].\n"
        "4. ONLY add tasks that are essential to address the critic's concerns.\n"
    )

    new_tasks_data = await agenerate_json(
        role="orchestrator",
        prompt=prompt,
        temperature=0.2,
        max_tokens=1000
    )

    tasks = list(state["tasks"])
    added_count = 0
    if new_tasks_data and isinstance(new_tasks_data, list):
        for t_data in new_tasks_data:
            if t_data.get("title") not in current_tasks:
                new_task: GraphTask = {
                    "task_id": f"dyn-{len(tasks) + 1}",
                    "title": t_data.get("title", "New Task"),
                    "objective": t_data.get("objective", ""),
                    "depends_on": t_data.get("depends_on", []),
                    "status": "pending"
                }
                tasks.append(new_task)
                added_count += 1

    await apublish_progress(
        agent="Replanner",
        status="complete",
        detail=f"Added {added_count} new tasks",
        message="Roadmap updated",
    )
    
    return {
        "tasks": tasks,
        "phase": "replanned" if added_count > 0 else "replan_skipped"
    }
