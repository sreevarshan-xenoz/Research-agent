from __future__ import annotations

from research_agent.orchestration.state import GraphState


def planner_node(state: GraphState) -> dict:
    topic = state["topic"]
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
    return {"tasks": tasks, "phase": "planned"}
