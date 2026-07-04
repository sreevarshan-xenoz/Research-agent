from __future__ import annotations

import logging
from typing import Any

from research_agent.models import agenerate_json

logger = logging.getLogger(__name__)

_REFINEMENT_PROMPT = """You are a research methodologist analyzing search results to identify gaps.

Topic: {topic}
Task: {task_title}
Task Objective: {task_objective}

## Current Search Results

{findings_summary}

## Current Search Queries Used

{queries_used}

## Analysis Instructions

Review the findings above. Identify:

1. **Coverage gaps** — Are there aspects of the task objective that have little or no information?
2. **Conflicting evidence** — Do sources disagree on any key claims?
3. **Shallow coverage** — Are any sections only supported by a single source?
4. **Missing perspectives** — Are there known methodological approaches or sub-topics not addressed?

## Output

Generate exactly 1-2 follow-up search queries that would fill the most important gaps.
Each query should be:
- Specific (not generic)
- Targeted to what's missing
- Likely to return new information not already covered

Return a JSON object with this structure:
{{
  "gaps_identified": ["Brief gap 1", "Brief gap 2"],
  "follow_up_queries": ["specific query 1", "specific query 2"]
}}

If no meaningful gaps remain (coverage is comprehensive), return:
{{"gaps_identified": [], "follow_up_queries": []}}
"""


async def refine_queries(
    topic: str,
    task_title: str,
    task_objective: str,
    current_findings: dict[str, Any],
    queries_used: list[str],
) -> list[str]:
    """Analyze current findings and generate follow-up search queries.

    Uses the orchestrator LLM (head model) to identify gaps and propose
    targeted follow-up queries. Returns an empty list when coverage is
    considered comprehensive (termination signal).
    """
    # Build a concise summary of current findings
    findings_parts: list[str] = []
    total_items = 0
    for provider, provider_data in current_findings.items():
        if not isinstance(provider_data, dict):
            continue
        items = provider_data.get("items", [])
        if not isinstance(items, list):
            continue
        total_items += len(items)
        snippets = []
        for item in items[:3]:  # Top 3 per provider
            title = str(item.get("title", "") or "")
            snippet = str(item.get("snippet", "") or "")
            if title and snippet:
                snippets.append(f"- {title}: {snippet[:200]}")
            elif title:
                snippets.append(f"- {title}")
        if snippets:
            findings_parts.append(f"[{provider}] ({len(items)} results):")
            findings_parts.extend(snippets)

    if not findings_parts:
        findings_parts = ["(No results found yet)"]

    findings_summary = "\n".join(findings_parts)

    prompt = _REFINEMENT_PROMPT.format(
        topic=topic,
        task_title=task_title,
        task_objective=task_objective,
        findings_summary=findings_summary,
        queries_used="\n".join(f"- {q}" for q in queries_used) if queries_used else "(Initial search)",
    )

    try:
        result = await agenerate_json(role="head", prompt=prompt, temperature=0.3, max_tokens=800)
        if result and isinstance(result, dict):
            queries = result.get("follow_up_queries", [])
            if isinstance(queries, list):
                return [str(q) for q in queries if q and str(q).strip()]
        return []
    except Exception as exc:
        logger.warning("Query refinement failed: %s", exc)
        return []
