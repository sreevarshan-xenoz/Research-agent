"""P26 — Hypothesis Generator: synthesizes novel research hypotheses from gaps.

Takes the gap analysis output + literature findings + topic and uses an LLM
to generate testable, novel hypotheses with rationale, methodology proposals,
and evaluation approaches.
"""

from __future__ import annotations

import logging

from research_agent.models import agenerate_json
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState

logger = logging.getLogger(__name__)

_Hypothesis = dict[str, object]

_HYPOTHESIS_FALLBACKS = [
    {
        "id": "h1",
        "title": "Cross-paradigm integration hypothesis",
        "hypothesis": "Integrating methodologies from adjacent paradigms will yield synergistic improvements exceeding individual contributions.",
        "rationale": "The literature shows strong results in individual approaches but limited cross-pollination. Combining strengths may unlock compound gains.",
        "gap_addressed": "methodology",
        "proposed_approach": "Design a hybrid framework that combines the top-performing methods from each paradigm and evaluates on standard benchmarks.",
        "evaluation_approach": "Ablation studies comparing the hybrid against each individual component",
        "required_resources": ["benchmark datasets", "baseline implementations", "compute for hyperparameter search"],
        "confidence": 0.45,
        "novelty_score": 0.7,
        "feasibility_score": 0.6,
    },
    {
        "id": "h2",
        "title": "Evaluation standardization hypothesis",
        "hypothesis": "Standardizing evaluation protocols across the field will reveal that many reported gains are attributable to evaluation variance rather than methodological improvement.",
        "rationale": "The gap analysis indicates inconsistent evaluation practices. A standardized benchmark could resolve contradictory findings.",
        "gap_addressed": "evaluation",
        "proposed_approach": "Implement a unified evaluation framework with standardized metrics, data splits, and statistical testing.",
        "evaluation_approach": "Re-evaluate 10+ published methods under the standardized framework and compare variance",
        "required_resources": ["code from published papers", "compute budget for re-evaluations", "statistical expertise"],
        "confidence": 0.55,
        "novelty_score": 0.6,
        "feasibility_score": 0.8,
    },
    {
        "id": "h3",
        "title": "Coverage expansion hypothesis",
        "hypothesis": "Underexplored application domains within this research area contain low-hanging fruit where existing methods can achieve strong results with minimal adaptation.",
        "rationale": "Most papers focus on a narrow set of benchmark applications. Adjacent domains remain unaddressed despite similar problem structure.",
        "gap_addressed": "coverage",
        "proposed_approach": "Survey adjacent domains, select 2-3 with high structural similarity, and apply the best-performing method with minimal modifications.",
        "evaluation_approach": "Domain-specific metrics and comparison to domain baselines",
        "required_resources": ["domain expertise or collaborators", "domain datasets", "baseline implementations"],
        "confidence": 0.5,
        "novelty_score": 0.65,
        "feasibility_score": 0.75,
    },
]


async def hypothesis_generator_node(state: GraphState) -> dict:
    """Generate novel testable hypotheses from gap analysis and literature findings.

    Analyzes the gap_analysis output together with the literature findings and
    topic context to propose concrete, falsifiable research hypotheses.
    """
    await apublish_progress(
        agent="Hypothesis Generator",
        status="running",
        detail="Analyzing gaps and literature",
        message="Generating novel research hypotheses",
    )

    topic = state.get("topic", "")
    gap_analysis = state.get("gap_analysis", [])
    findings = state.get("task_findings", {})

    # Build context from gap analysis
    gaps_context = ""
    if gap_analysis:
        gaps_context = "\n".join([
            f"- [{g.get('category', 'unknown')}] {g.get('description', '')} "
            f"(confidence: {g.get('confidence', 0)})"
            for g in gap_analysis[:5]
        ])

    # Build context from findings (number of papers, key methods, etc.)
    findings_dict: dict[str, dict[str, dict[str, list[dict[str, object]]]]] = findings  # type: ignore[assignment]
    paper_count = sum(
        len(provider_data.get("items", []))
        for task_data in findings_dict.values()
        for provider_data in task_data.values()
    )
    methods_found: set[str] = set()
    for task_data in findings_dict.values():
        for provider_data in task_data.values():
            for item in provider_data.get("items", []):
                text = (str(item.get("title", "") or "") + " " + str(item.get("snippet", "") or "")).lower()
                for kw in ["transformer", "cnn", "lstm", "graph", "attention", "diffusion", "gan", "vae", "reinforcement", "transfer", "few-shot", "zero-shot", "prompt", "fine-tune", "pretrain"]:
                    if kw in text:
                        methods_found.add(kw)

    depth = state.get("depth", "balanced")
    num_hypotheses = {"quick": 2, "balanced": 3, "deep": 5}.get(depth, 3)

    prompt = (
        f"You are a creative and rigorous research scientist. Given the following research topic, "
        f"gap analysis, and literature context, generate {num_hypotheses} novel, testable hypotheses.\n\n"
        f"## Research Topic\n{topic}\n\n"
        f"## Gap Analysis\n{gaps_context or 'No structured gap analysis available. Infer gaps from the topic.'}\n\n"
        f"## Literature Context\n"
        f"- Papers analyzed: {paper_count}\n"
        f"- Methods identified: {', '.join(sorted(methods_found)) or 'various'}\n\n"
        f"## Instructions\n"
        f"For each hypothesis, provide:\n"
        f"1. A clear, falsifiable hypothesis statement\n"
        f"2. Rationale connecting it to identified gaps\n"
        f"3. A concrete proposed approach/methodology\n"
        f"4. An evaluation approach with specific metrics\n"
        f"5. Required resources\n"
        f"6. Novelty score (0.0-1.0)\n"
        f"7. Feasibility score (0.0-1.0)\n\n"
        f"Return a JSON object with a 'hypotheses' key containing an array of hypothesis objects. "
        f"Each object must have: 'id' (string like 'h1'), 'title', 'hypothesis' (the main statement), "
        f"'rationale', 'gap_addressed', 'proposed_approach', 'evaluation_approach', "
        f"'required_resources' (array of strings), 'novelty_score', 'feasibility_score'."
    )

    hypotheses = list(_HYPOTHESIS_FALLBACKS)

    # Try LLM generation
    llm_result = await agenerate_json(
        role="orchestrator",
        prompt=prompt,
        temperature=0.7,
        max_tokens=3000,
    )

    if llm_result and isinstance(llm_result, dict) and "hypotheses" in llm_result:
        raw = llm_result["hypotheses"]
        if isinstance(raw, list) and len(raw) > 0:
            valid: list[dict[str, object]] = []
            for h in raw:
                if isinstance(h, dict) and "title" in h and "hypothesis" in h:
                    h.setdefault("id", f"h{len(valid) + 1}")
                    h.setdefault("rationale", "")
                    h.setdefault("gap_addressed", "general")
                    h.setdefault("proposed_approach", "")
                    h.setdefault("evaluation_approach", "")
                    h.setdefault("required_resources", [])
                    h.setdefault("novelty_score", 0.5)
                    h.setdefault("feasibility_score", 0.5)
                    valid.append(h)
            if valid:
                hypotheses = valid

    await apublish_progress(
        agent="Hypothesis Generator",
        status="complete",
        detail=f"Generated {len(hypotheses)} hypotheses",
        message=f"{len(hypotheses)} novel hypotheses ready",
    )

    return {"generated_hypotheses": hypotheses, "phase": "hypotheses_generated"}
