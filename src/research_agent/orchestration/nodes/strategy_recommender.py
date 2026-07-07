"""P26 — Strategy Recommender: suggests research methodology, datasets, and baselines.

Analyzes the research topic + depth + existing findings and recommends:
- Methodological approaches (which methods/architectures to use)
- Datasets (which datasets are appropriate for evaluation)
- Baselines (which existing methods to compare against)
- Evaluation metrics (which metrics to report)
"""

from __future__ import annotations

import logging

from research_agent.models import agenerate_json
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState

logger = logging.getLogger(__name__)

_FindingDict = dict[str, dict[str, dict[str, list[dict[str, object]]]]]

_FALLBACK_STRATEGY = {
    "methodology": {
        "recommended_approaches": [
            {
                "name": "Literature-informed baseline approach",
                "description": "Adopt the most cited methodology from related work as baseline, then extend with targeted innovations addressing identified gaps.",
                "rationale": "Following established methodology ensures comparability; targeted innovations maximize impact.",
            },
        ],
        "avoid": ["Overly complex pipelines without clear ablation justification"],
    },
    "datasets": {
        "recommended": [
            {
                "name": "Standard benchmark datasets",
                "description": "Use the most widely adopted datasets in the field for comparability.",
                "rationale": "Standard benchmarks enable direct comparison with published results.",
            },
        ],
        "consider": ["Domain-specific datasets if the research targets a particular application area"],
    },
    "baselines": {
        "recommended": [
            {
                "name": "State-of-the-art methods",
                "description": "Compare against the top-3 performing methods identified in the literature.",
                "rationale": "SOTA comparison demonstrates the value proposition of the proposed approach.",
            },
        ],
        "minimal": ["At minimum, compare against a simple baseline and a strong baseline"],
    },
    "evaluation": {
        "primary_metrics": ["Accuracy / F1 / AUC depending on task type"],
        "statistical_tests": ["Report confidence intervals and statistical significance tests"],
        "ablation": ["Ablation studies for each component of the proposed method"],
    },
}


async def strategy_recommender_node(state: GraphState) -> dict:
    """Generate research strategy recommendations for the given topic and findings.

    Analyzes the topic, depth setting, and any existing findings to recommend
    methodologies, datasets, baselines, and evaluation approaches.
    """
    await apublish_progress(
        agent="Strategy Recommender",
        status="running",
        detail="Analyzing research landscape",
        message="Recommending research strategy",
    )

    topic = state.get("topic", "")
    depth = state.get("depth", "balanced")
    findings = state.get("task_findings", {})

    # Extract methods and datasets mentioned in findings
    methods_mentioned: set[str] = set()
    datasets_mentioned: set[str] = set()
    venues_mentioned: set[str] = set()

    findings_dict: _FindingDict = findings  # type: ignore[assignment]
    for task_data in findings_dict.values():
        for provider_data in task_data.values():
            for item in provider_data.get("items", []):
                text = (str(item.get("title", "") or "") + " " + str(item.get("snippet", "") or "") + " " + str(item.get("content", "") or "")).lower()
                # Detect methods
                for kw in ["transformer", "cnn", "rnn", "lstm", "graph neural", "attention", "diffusion",
                           "gan", "vae", "bert", "gpt", "resnet", "vit", "llm", "foundation model",
                           "reinforcement learning", "transfer learning", "few-shot", "zero-shot",
                           "contrastive learning", "self-supervised"]:
                    if kw in text:
                        methods_mentioned.add(kw)
                # Detect datasets
                for ds_kw in ["imagenet", "coco", "squad", "glue", "superglue", "mnist", "cifar",
                              "wikipedia", "common crawl", "pubmed", "arxiv", "cityscapes",
                              "kinetics", "librispeech", "wikitext"]:
                    if ds_kw in text:
                        datasets_mentioned.add(ds_kw)
                # Detect venues
                venue = str(item.get("journal", "") or "") or str(item.get("venue", "") or "")
                if venue:
                    venues_mentioned.add(venue)

    prompt = (
        f"You are a senior research advisor. Given a research topic and findings, "
        f"recommend the optimal research strategy.\n\n"
        f"## Research Topic\n{topic}\n\n"
        f"## Research Depth\n{depth} (quick=overview, balanced=standard paper, deep=comprehensive)\n\n"
        f"## Methods Identified in Literature\n{', '.join(sorted(methods_mentioned)) or 'None specifically identified'}\n\n"
        f"## Datasets Identified\n{', '.join(sorted(datasets_mentioned)) or 'None specifically identified'}\n\n"
        f"## Key Venues\n{', '.join(sorted(venues_mentioned)[:5]) or 'Not specified'}\n\n"
        f"## Instructions\n"
        f"Return a JSON object with the following structure:\n"
        f"{{\n"
        f'  "methodology": {{\n'
        f'    "recommended_approaches": [{{"name": "...", "description": "...", "rationale": "..."}}],\n'
        f'    "avoid": ["..."],\n'
        f'  }},\n'
        f'  "datasets": {{\n'
        f'    "recommended": [{{"name": "...", "description": "...", "rationale": "..."}}],\n'
        f'    "consider": ["..."],\n'
        f'  }},\n'
        f'  "baselines": {{\n'
        f'    "recommended": [{{"name": "...", "description": "...", "rationale": "..."}}],\n'
        f'    "minimal": ["..."],\n'
        f'  }},\n'
        f'  "evaluation": {{\n'
        f'    "primary_metrics": ["..."],\n'
        f'    "statistical_tests": ["..."],\n'
        f'    "ablation": ["..."],\n'
        f'  }}\n'
        f"}}\n\n"
        f"Be specific and actionable. If literature mentions specific datasets or methods, reference them."
    )

    strategy = dict(_FALLBACK_STRATEGY)  # Deep copy

    llm_result = await agenerate_json(
        role="orchestrator",
        prompt=prompt,
        temperature=0.3,
        max_tokens=2500,
    )

    if llm_result and isinstance(llm_result, dict):
        for key in ["methodology", "datasets", "baselines", "evaluation"]:
            if key in llm_result and isinstance(llm_result[key], dict):
                strategy[key] = llm_result[key]

    await apublish_progress(
        agent="Strategy Recommender",
        status="complete",
        detail="Strategy generated",
        message="Research strategy ready",
    )

    return {"research_strategy": strategy, "phase": "strategy_recommended"}
