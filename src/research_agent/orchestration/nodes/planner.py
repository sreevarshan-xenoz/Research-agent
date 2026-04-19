from __future__ import annotations

from research_agent.models import generate_json
from research_agent.observability import publish_progress
from research_agent.orchestration.state import GraphState


def planner_node(state: GraphState) -> dict:
    topic = state["topic"]
    publish_progress(
        agent="Planner",
        status="running",
        detail="Building task graph",
        message="Planning research subtasks",
    )

    # Fallback default tasks used when head model is unavailable or fails
    tasks = [
        {
            "task_id": "t1",
            "title": "Background and scope",
            "objective": f"Establish context, definitions, and boundaries for: {topic}",
            "depends_on": [],
            "status": "pending",
        },
        {
            "task_id": "t2",
            "title": "Official paper collection",
            "objective": f"Collect and triage official papers relevant to: {topic}",
            "depends_on": [],
            "status": "pending",
        },
        {
            "task_id": "t3",
            "title": "Method and evidence analysis",
            "objective": f"Analyze methodologies and evidence quality for: {topic}",
            "depends_on": ["t2"],
            "status": "pending",
        },
        {
            "task_id": "t4",
            "title": "Synthesis draft inputs",
            "objective": f"Prepare section-ready findings and citation links for: {topic}",
            "depends_on": ["t1", "t3"],
            "status": "pending",
        },
    ]

    prompt = (
        f"Decompose the following research topic into 4-6 specific sub-research tasks: '{topic}'.\n"
        "Each task must have a 'task_id' (e.g. t1, t2), 'title', 'objective', and 'depends_on' (a list of other task_ids).\n"
        "Ensure the tasks form a valid Directed Acyclic Graph (DAG).\n"
        "Return a JSON object with a 'tasks' key containing the list of task objects."
    )

    # Use the HEAD model (local Ollama) for task planning
    llm_plan = generate_json(role="head", prompt=prompt)
    if llm_plan and isinstance(llm_plan, dict) and "tasks" in llm_plan:
        raw_tasks = llm_plan["tasks"]
        valid_tasks = []
        for t in raw_tasks:
            if isinstance(t, dict) and all(k in t for k in ("task_id", "title", "objective")):
                t["status"] = "pending"
                t["depends_on"] = t.get("depends_on", [])
                if not isinstance(t["depends_on"], list):
                    t["depends_on"] = []
                valid_tasks.append(t)
        if valid_tasks:
            tasks = valid_tasks

    publish_progress(
        agent="Planner",
        status="complete",
        detail=f"Planned {len(tasks)} tasks",
        message="Task graph ready",
    )
    return {"tasks": tasks, "phase": "planned"}
