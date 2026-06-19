from research_agent.observability import apublish_progress
from research_agent.orchestration.nodes.indexing import get_contradiction_links
from research_agent.orchestration.state import GraphState, GraphTask


async def critic_node(state: GraphState) -> dict:
    await apublish_progress(
        agent="Critic",
        status="running",
        detail="Scoring evidence confidence",
        message="Reviewing evidence quality",
    )
    section_confidence: dict[str, float] = {}
    notes: list[str] = []

    from research_agent.config import load_settings
    settings = load_settings()
    metadata_penalty = float(settings.retrieval.metadata_fallback_confidence_penalty)

    tasks: list[GraphTask] = [t.copy() for t in state["tasks"]]
    iteration_index = state["iteration_index"] + 1
    contradiction_links = await get_contradiction_links(state["run_id"])

    def _get_int(provider_data: dict[str, object], key: str) -> int:
        val = provider_data.get(key, 0)
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str) and val.isdigit():
            return int(val)
        return 0

    low_confidence_tasks = []
    for task in tasks:
        task_id = str(task["task_id"])
        findings = state["task_findings"].get(task_id, {})

        item_count = sum(_get_int(provider_data, "item_count") for provider_data in findings.values())
        warning_count = sum(
            _get_int(provider_data, "warning_count") for provider_data in findings.values()
        )
        metadata_only_count = sum(
            _get_int(provider_data, "metadata_only_count") for provider_data in findings.values()
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
                    - (metadata_only_count * metadata_penalty)
                    - contradiction_penalty,
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
    
    # If we have low confidence and capacity for more iterations, mark ONLY those tasks for re-run
    await apublish_progress(
        agent="Critic",
        status="running",
        detail=f"Iteration {iteration_index}/{state['max_iterations']}: {len(low_confidence_tasks)} low-confidence tasks",
        message="Evaluating loop diagnostics",
    )

    if low_confidence_tasks and iteration_index < state["max_iterations"]:
        await apublish_progress(
            agent="Critic",
            status="running",
            detail=f"Resetting {len(low_confidence_tasks)} low-confidence tasks for iteration {iteration_index}",
            message="Planning iteration loop",
        )
        
        # Mark low-confidence tasks as pending so worker_executor picks them up
        low_conf_ids = {str(t["task_id"]) for t in low_confidence_tasks}
        for t in tasks:
            if str(t["task_id"]) in low_conf_ids:
                t["status"] = "pending"

        depends_on_originals = [str(t["task_id"]) for t in low_confidence_tasks]
        new_tasks: list[GraphTask] = [
            {
                "task_id": f"f{iteration_index}",
                "title": "Deep evidence recovery",
                "objective": f"Recover missing evidence for: {state['topic']}",
                "depends_on": depends_on_originals,
                "status": "pending",
            }
        ]
        tasks.extend(new_tasks)
    elif low_confidence_tasks:
        # At max iterations but still low confidence — will be handled by routing logic
        await apublish_progress(
            agent="Critic",
            status="running",
            detail=f"Max iterations ({state['max_iterations']}) reached with {len(low_confidence_tasks)} low-confidence tasks",
            message="Loop limit reached, proceeding to synthesis",
        )
        notes.append(
            f"Max iterations ({state['max_iterations']}) reached — "
            f"{len(low_confidence_tasks)} task(s) still have low confidence"
        )

    await apublish_progress(
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
