"""P26 — Proactive Gap Filling / Gap Exploration.

When the literature is thin or evidence density is low, this node:
1. Analyzes why literature is thin (new field, niche topic, search failure)
2. Suggests pilot experiments or targeted search strategies
3. Returns gap exploration notes that feed back into the worker loop
"""

from __future__ import annotations

import logging

from research_agent.models import agenerate_json
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState

logger = logging.getLogger(__name__)

_DensityDict = dict[str, object]
_FindingDict = dict[str, dict[str, dict[str, list[dict[str, object]]]]]


def _compute_evidence_density(state: GraphState) -> _DensityDict:
    """Compute evidence density metrics from current task findings."""
    findings: _FindingDict = state.get("task_findings", {})  # type: ignore[assignment]
    total_items = 0
    provider_counts: dict[str, int] = {}
    seen_titles: set[str] = set()

    for task_data in findings.values():
        for provider_name, provider_data in task_data.items():
            items: list[dict[str, object]] = provider_data.get("items", [])
            provider_counts[provider_name] = provider_counts.get(provider_name, 0) + len(items)
            for item in items:
                title = str(item.get("title", "") or "")
                if title:
                    seen_titles.add(title)
            total_items += len(items)

    depth = state.get("depth", "balanced")
    expected_thresholds = {"quick": 10, "balanced": 20, "deep": 40}
    expected = expected_thresholds.get(depth, 20)

    return {
        "total_items": total_items,
        "unique_papers": len(seen_titles),
        "provider_diversity": len(provider_counts),
        "expected_threshold": expected,
        "is_thin": total_items < expected,
        "provider_breakdown": provider_counts,
    }


async def gap_exploration_node(state: GraphState) -> dict:
    """Analyze literature density and propose gap-filling actions.

    When the literature is thin, this node generates:
    - An analysis of why the literature is thin
    - Proposed pilot experiments or alternative search strategies
    - New search queries for the worker layer to execute
    """
    await apublish_progress(
        agent="Gap Explorer",
        status="running",
        detail="Analyzing evidence density",
        message="Proactive gap filling",
    )

    density = _compute_evidence_density(state)
    topic = state.get("topic", "")

    gap_exploration = {
        "evidence_density": density,
        "is_thin": density["is_thin"],
        "analysis": "",
        "pilot_experiments": [],
        "alternative_queries": [],
        "recommendation": "",
    }

    if not density["is_thin"]:
        gap_exploration["analysis"] = "Literature appears sufficient for the current depth setting."
        gap_exploration["recommendation"] = "proceed"
        await apublish_progress(
            agent="Gap Explorer",
            status="complete",
            detail="Evidence density adequate",
            message="No gap filling needed",
        )
        return {
            "gap_exploration": gap_exploration,
            "phase": "gap_exploration_skipped",
        }

    # Literature is thin — try LLM to generate exploration plan
    prompt = (
        f"You are a research strategist. The literature for the topic '{topic}' is thin "
        f"(only {density['total_items']} items found across {density['provider_diversity']} sources, "
        f"expecting at least {density['expected_threshold']}).\n\n"
        f"## Analysis Tasks\n"
        f"1. Diagnose WHY the literature is thin: new field? niche sub-topic? search strategy issue? "
        f"terminology mismatch?\n"
        f"2. Propose 2-3 pilot experiments or preliminary studies that could be conducted even with limited literature.\n"
        f"3. Suggest 3-5 alternative search queries that might find more relevant literature "
        f"(different terminology, adjacent fields, broader/narrower terms).\n"
        f"4. Provide a recommendation: should we continue with what we have, change search strategy, "
        f"or pivot the research angle?\n\n"
        f"Return a JSON object with keys: 'analysis', 'pilot_experiments' (array of strings), "
        f"'alternative_queries' (array of strings), 'recommendation' (one of: "
        f"'proceed_with_caveats', 'change_search_strategy', 'pivot_topic')."
    )

    llm_result = await agenerate_json(
        role="orchestrator",
        prompt=prompt,
        temperature=0.5,
        max_tokens=2000,
    )

    if llm_result and isinstance(llm_result, dict):
        if "analysis" in llm_result:
            gap_exploration["analysis"] = llm_result["analysis"]
        if "pilot_experiments" in llm_result and isinstance(llm_result["pilot_experiments"], list):
            gap_exploration["pilot_experiments"] = [
                str(e) for e in llm_result["pilot_experiments"] if e
            ]
        if "alternative_queries" in llm_result and isinstance(llm_result["alternative_queries"], list):
            gap_exploration["alternative_queries"] = [
                str(q) for q in llm_result["alternative_queries"] if q
            ]
        if "recommendation" in llm_result:
            rec = str(llm_result["recommendation"])
            if rec in ("proceed_with_caveats", "change_search_strategy", "pivot_topic"):
                gap_exploration["recommendation"] = rec
    else:
        # Fallback if LLM fails
        gap_exploration["analysis"] = (
            f"Limited literature found ({density['total_items']} items). "
            f"This may be a niche or emerging topic. Consider broadening search terms."
        )
        gap_exploration["pilot_experiments"] = [
            "Conduct a systematic literature review with broader search criteria",
            "Perform a preliminary analysis on available data to identify patterns",
        ]
        gap_exploration["alternative_queries"] = [
            f"{topic} survey",
            f"{topic} review",
            f"{topic} recent advances",
        ]
        gap_exploration["recommendation"] = "change_search_strategy"

    await apublish_progress(
        agent="Gap Explorer",
        status="complete",
        detail=f"Thin literature analysis: {gap_exploration['recommendation']}",
        message=f"Proactive gap analysis: {str(gap_exploration['recommendation']).replace('_', ' ').title()}",
    )

    return {
        "gap_exploration": gap_exploration,
        "phase": "gap_exploration_complete",
    }
