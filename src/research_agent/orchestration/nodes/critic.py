import os

from research_agent.config import load_settings
from research_agent.models import generate_json_with_nvidia
from research_agent.observability import publish_progress
from research_agent.orchestration.nodes.indexing import get_contradiction_links
from research_agent.orchestration.state import GraphState


def critic_node(state: GraphState) -> dict:
    publish_progress(
        agent="Critic",
        status="running",
        detail="Scoring evidence confidence",
        message="Reviewing evidence quality",
    )
    section_confidence: dict[str, float] = {}
    notes: list[str] = []
    settings = load_settings()
    metadata_penalty = float(settings.retrieval.metadata_fallback_confidence_penalty)
    tasks = [dict(t) for t in state["tasks"]]
    iteration_index = state["iteration_index"] + 1
    contradiction_links = get_contradiction_links(state["run_id"])

    low_confidence_tasks = []
    for task in tasks:
        task_id = str(task["task_id"])
        findings = state["task_findings"].get(task_id, {})

        item_count = sum(int(provider_data.get("item_count", 0)) for provider_data in findings.values())
        warning_count = sum(
            int(provider_data.get("warning_count", 0)) for provider_data in findings.values()
        )
        metadata_only_count = sum(
            int(provider_data.get("metadata_only_count", 0)) for provider_data in findings.values()
        )
        contradiction_count = sum(
            1
            for link in contradiction_links
            if task_id in {link.get("task_a", ""), link.get("task_b", "")}
        )
        contradiction_penalty = min(0.2, contradiction_count * 0.05)

        if item_count == 0:
            confidence = 0.1
        else:
            confidence = max(
                0.0,
                min(
                    1.0,
                    (item_count / 8.0)
                    - (warning_count * 0.04)
                    - (metadata_only_count * metadata_penalty),
                    - contradiction_penalty
                ),
            )

        section_confidence[task_id] = round(confidence, 3)
        if confidence < 0.35:
            notes.append(f"Low evidence confidence for {task_id}")
            low_confidence_tasks.append(task)
        if metadata_only_count > 0:
            notes.append(f"Metadata fallback penalty applied for {task_id} ({metadata_only_count} items)")
        if contradiction_count > 0:
            notes.append(
                f"Contradiction penalty applied for {task_id} "
                f"({contradiction_count} conflicting links)"
            )

    if not notes:
        notes.append("Evidence confidence is acceptable for initial v1 synthesis")
    
    # If we have low confidence and capacity for more iterations, generate new tasks
    if low_confidence_tasks and iteration_index < state["max_iterations"]:
        publish_progress(
            agent="Critic",
            status="running",
            detail="Generating follow-up tasks",
            message="Planning iteration loop",
        )
        model_name = os.getenv("NVIDIA_MODEL") or settings.models.strong_model
        
        low_conf_str = "\n".join([f"- {t['title']}: {t['objective']}" for t in low_confidence_tasks])
        prompt = (
            f"The following research tasks for the topic '{state['topic']}' had low evidence quality:\n"
            f"{low_conf_str}\n\n"
            "Generate 1-3 specific follow-up research tasks to address these gaps. "
            "Each task must have a 'task_id' (unique, e.g. f1, f2), 'title', 'objective', and 'depends_on' (list).\n"
            "Return a JSON object with a 'tasks' key."
        )
        
        llm_followup = generate_json_with_nvidia(model=model_name, prompt=prompt)
        new_tasks = []
        if llm_followup and isinstance(llm_followup, dict) and "tasks" in llm_followup:
            new_tasks = llm_followup["tasks"]
        else:
            # Fallback follow-up tasks
            new_tasks = [
                {
                    "task_id": f"f{iteration_index}",
                    "title": "Deep evidence recovery",
                    "objective": f"Recover missing evidence for: {state['topic']}",
                    "depends_on": [],
                }
            ]

        for t in new_tasks:
            t["status"] = "pending"
            tasks.append(t)

    publish_progress(
        agent="Critic",
        status="complete",
        detail="Confidence scoring done",
        message="Critic completed",
    )
    return {
        "section_confidence": section_confidence,
        "critic_notes": notes,
        "phase": "critic_scored",
        "tasks": tasks,
        "iteration_index": iteration_index,
    }
