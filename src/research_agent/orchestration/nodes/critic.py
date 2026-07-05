from __future__ import annotations

from research_agent.models import run_json_ensemble
from research_agent.observability import apublish_progress
from research_agent.orchestration.nodes.indexing import get_contradiction_links
from research_agent.orchestration.state import GraphState, GraphTask
from research_agent.orchestration.deep_research.evidence_scorer import score_evidence
from research_agent.orchestration.deep_research.termination import check_termination


async def critic_node(state: GraphState) -> dict:
    await apublish_progress(
        agent="Critic",
        status="running",
        detail="Scoring evidence confidence (multi-factor)",
        message="Reviewing evidence quality",
    )
    section_confidence: dict[str, float] = {}
    notes: list[str] = []
    termination_signals: dict[str, str] = dict(state.get("termination_signals", {}))

    tasks: list[GraphTask] = [t.copy() for t in state["tasks"]]
    iteration_index = state["iteration_index"] + 1
    contradiction_links = await get_contradiction_links(state["run_id"])
    deep_research_enabled = state.get("depth", "balanced") in ("deep", "comprehensive")

    # P31: Multi-Model Ensemble Voting for critic confidence scoring
    from research_agent.config import load_settings
    _settings = load_settings()
    ensemble_enabled = _settings.ensemble.enabled and "critic" in _settings.ensemble.task_overrides

    low_confidence_tasks = []
    for task in tasks:
        task_id = str(task["task_id"])
        findings = state["task_findings"].get(task_id, {})

        if findings and isinstance(findings, dict):
            # Compute contradiction count for this task
            contradiction_count = sum(
                1
                for link in contradiction_links
                if task_id in {link.get("task_a", ""), link.get("task_b", "")}
            )

            # P21: Multi-factor evidence scoring
            evidence = score_evidence(
                findings,
                contradiction_count=contradiction_count,
            )
            confidence = evidence.overall

            # P31: Ensemble voting for critic confidence
            if ensemble_enabled and evidence.num_sources >= 3:
                ensemble_prompt = (
                    f"Rate the quality and completeness of evidence for research task '{task_id}' on topic '{state['topic']}'.\n"
                    f"Sources found: {evidence.num_sources}, Providers: {evidence.num_providers}\n"
                    f"Coverage: {evidence.coverage:.2f}, Source authority: {evidence.source_authority:.2f}\n"
                    "Output a JSON object with:\n"
                    "  - 'score': float 0.0-1.0 (overall evidence quality)\n"
                    "  - 'confidence': float 0.0-1.0 (your confidence in this score)\n"
                    "  - 'needs_more_research': bool (whether more research is needed)\n"
                )
                ensemble_result = await run_json_ensemble(
                    task_type="critic",
                    prompt=ensemble_prompt,
                    temperature=0.2,
                    max_tokens=512,
                )
                if ensemble_result.num_success >= 2 and ensemble_result.aggregated_json:
                    agg = ensemble_result.aggregated_json
                    if isinstance(agg, dict):
                        ensemble_score = agg.get("score") or agg.get("confidence")
                        if ensemble_score is not None:
                            confidence = float(ensemble_score)
                        if agg.get("needs_more_research"):
                            notes.append(f"Ensemble suggests more research needed for {task_id}")
                    notes.append(
                        f"Ensemble consensus for {task_id}: "
                        f"{ensemble_result.consensus_score:.2f} "
                        f"({ensemble_result.num_success}/{ensemble_result.num_models} models)"
                    )

            # Build rich critic notes
            if evidence.num_sources == 0:
                notes.append(f"No sources found for {task_id}")
            if evidence.coverage < 0.3:
                notes.append(f"Low coverage for {task_id} ({evidence.num_sources} sources)")
            if evidence.source_authority < 0.4:
                notes.append(f"Low source authority for {task_id}")
            if evidence.contradiction_penalty > 0:
                notes.append(
                    f"Contradiction penalty for {task_id}: "
                    f"{evidence.contradiction_penalty:.2f}"
                )
            if evidence.num_providers <= 1 and evidence.num_sources > 0:
                notes.append(f"Single provider dependency for {task_id}")

            # Deep research termination check
            # Primary termination handled by worker's iterative refinement;
            # critic-level termination is a secondary safety net using empty
            # previous_scores (the worker's query_refiner returns empty when
            # coverage is sufficient).
            if deep_research_enabled and task_id in state.get("task_findings", {}):
                term_decision = check_termination(
                    current_overall=evidence.overall,
                    current_coverage=evidence.coverage,
                    current_total_items=evidence.num_sources,
                    previous_scores=[],
                    round_index=iteration_index,
                )
                if term_decision.should_terminate:
                    termination_signals[task_id] = term_decision.reason
                    notes.append(
                        f"Search terminated for {task_id}: {term_decision.reason}"
                    )
        else:
            # Fallback: no findings at all
            evidence = score_evidence({})
            confidence = evidence.overall
            notes.append(f"No findings data for {task_id}")

        section_confidence[task_id] = round(confidence, 3)
        if confidence < 0.35:
            low_confidence_tasks.append(task)

    if not notes:
        notes.append("Evidence confidence is acceptable for initial synthesis")

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
        "termination_signals": termination_signals,
    }
