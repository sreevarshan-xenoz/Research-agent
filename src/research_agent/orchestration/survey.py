from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from research_agent.models import agenerate_json, agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.nodes.worker import WorkerPool
from research_agent.tools.base import BaseToolAdapter
from research_agent.tools.registry import arun_multi_source_search
from research_agent.output.survey_generator import (
    generate_survey_paper,
    generate_taxonomy_table,
    generate_timeline,
    generate_research_landscape,
)


logger = logging.getLogger(__name__)


@dataclass
class SurveyTopic:
    """Represents a single sub-topic within the survey."""
    name: str
    description: str
    task_id: str = ""
    findings: dict[str, Any] = field(default_factory=dict)
    key_papers: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""


@dataclass
class SurveyResult:
    """Output of a survey generation run."""
    run_id: str
    topic: str
    sub_topics: list[SurveyTopic]
    survey_markdown: str
    taxonomy_table: str
    timeline: str
    research_landscape: str
    key_findings: list[str]
    paper_count: int
    duration_seconds: float
    warnings: list[str]


SURVEY_SECTIONS = [
    "introduction",
    "background",
    "taxonomy",
    "comparative_analysis",
    "challenges",
    "future_directions",
    "conclusion",
]


async def plan_survey_topics(
    broad_topic: str,
    num_topics: int = 5,
) -> list[SurveyTopic]:
    """Use LLM to decompose a broad topic into specific sub-topics for survey coverage.

    Args:
        broad_topic: The broad research area to survey (e.g. "Large Language Models").
        num_topics: Number of sub-topics to generate.

    Returns:
        List of SurveyTopic objects with names and descriptions.
    """
    await apublish_progress(
        agent="Survey Planner",
        status="running",
        detail="Decomposing research area",
        message="Planning survey topics",
    )

    prompt = (
        f"Decompose the following broad research area into {num_topics} specific sub-topics "
        f"for a comprehensive survey paper:\n\n'{broad_topic}'\n\n"
        "For each sub-topic, provide:\n"
        "- 'name': A short, specific name (e.g. 'Transformer Architectures')\n"
        "- 'description': A 1-2 sentence description of what this sub-topic covers\n\n"
        "Ensure the sub-topics collectively cover the major areas of the field. "
        "Return a JSON object with a 'topics' key containing the list of topic objects."
    )

    llm_result = await agenerate_json(role="head", prompt=prompt)
    topics: list[SurveyTopic] = []

    if llm_result and isinstance(llm_result, dict) and "topics" in llm_result:
        for i, t in enumerate(llm_result["topics"]):
            if isinstance(t, dict) and "name" in t:
                topics.append(
                    SurveyTopic(
                        name=t["name"],
                        description=t.get("description", ""),
                        task_id=f"survey_t{i+1}",
                    )
                )

    # Fallback if LLM fails
    if not topics:
        fallback_topics = [
            "Background and Fundamentals",
            "Core Methodologies",
            "Key Architectures",
            "Applications and Use Cases",
            "Evaluation and Benchmarks",
            "Challenges and Limitations",
            "Future Directions",
        ]
        for i, name in enumerate(fallback_topics[:num_topics]):
            topics.append(
                SurveyTopic(
                    name=name,
                    description=f"Survey coverage of {name.lower()} related to {broad_topic}",
                    task_id=f"survey_t{i+1}",
                )
            )

    await apublish_progress(
        agent="Survey Planner",
        status="complete",
        detail=f"Planned {len(topics)} sub-topics",
        message="Survey topics ready",
    )
    return topics


async def research_survey_topics(
    topics: list[SurveyTopic],
    registry: dict[str, BaseToolAdapter],
) -> list[SurveyTopic]:
    """Research each survey sub-topic in parallel using existing WorkerPool.

    Args:
        topics: List of survey topics to research.
        registry: Tool registry for web/paper searches.
        progress_handler: Optional progress callback.

    Returns:
        List of SurveyTopic objects enriched with findings.
    """
    pool = WorkerPool(max_workers=min(len(topics), 6))

    async def research_topic(topic: SurveyTopic) -> SurveyTopic:
        await apublish_progress(
            agent=f"Survey Research: {topic.name}",
            status="running",
            detail=f"Researching: {topic.name}",
            message=f"Gathering papers on {topic.name}",
        )

        query = f"{topic.name}: {topic.description}"
        try:
            result_map = await arun_multi_source_search(
                query=query,
                registry=registry,
                limit=8,
            )
            topic.findings = {
                provider: {
                    "item_count": len(result.items),
                    "items": result.items,
                    "warnings": result.warnings,
                }
                for provider, result in result_map.items()
            }

            # Collect key papers
            for provider, result in result_map.items():
                for item in result.items:
                    if isinstance(item, dict) and item.get("title"):
                        topic.key_papers.append(item)

        except Exception as e:
            logger.warning("Survey research failed for %s: %s", topic.name, e)
            topic.findings = {"error": {"items": [], "warnings": [str(e)]}}

        await apublish_progress(
            agent=f"Survey Research: {topic.name}",
            status="complete",
            detail=f"{len(topic.key_papers)} papers found",
            message=f"Completed research on {topic.name}",
        )
        return topic

    # Execute all topic research in parallel
    return await asyncio.gather(*[research_topic(t) for t in topics])


async def generate_summaries(
    topics: list[SurveyTopic],
) -> list[SurveyTopic]:
    """Generate a concise summary for each topic's findings using LLM.

    Args:
        topics: Survey topics with findings populated.

    Returns:
        Updated topics with LLM-generated summaries.
    """
    for topic in topics:
        if not topic.key_papers:
            topic.summary = f"No papers found for {topic.name}."
            continue

        paper_list = "\n".join(
            f"- {p.get('title', 'Untitled')} ({p.get('year', 'n.d.')})"
            for p in topic.key_papers[:10]
        )

        prompt = (
            f"Summarize the key findings and trends in the research area: {topic.name}\n\n"
            f"Context: {topic.description}\n\n"
            f"Key Papers:\n{paper_list}\n\n"
            "Write a concise 2-3 paragraph summary covering:\n"
            "1. The main research directions in this area\n"
            "2. Key findings or consensus points\n"
            "3. Open questions or debates\n"
        )

        summary = await agenerate_text(
            role="subagent",
            prompt=prompt,
            temperature=0.3,
            max_tokens=500,
        )
        topic.summary = summary or f"Summary unavailable for {topic.name}."

    return topics


async def identify_cross_cutting_themes(
    topics: list[SurveyTopic],
    broad_topic: str,
) -> list[str]:
    """Identify key findings and cross-cutting themes across all sub-topics.

    Args:
        topics: Survey topics with summaries.
        broad_topic: The original broad research area.

    Returns:
        List of key findings as strings.
    """
    summaries_text = "\n\n".join(
        f"## {t.name}\n{t.summary}"
        for t in topics
    )

    prompt = (
        f"Based on the following research summaries for the broad area '{broad_topic}',\n"
        "identify 5-8 key cross-cutting findings, trends, or insights that emerge\n"
        "across multiple sub-topics. These will form the key contributions of a survey paper.\n\n"
        f"Summaries:\n{summaries_text}\n\n"
        "Return a JSON object with a 'findings' key containing a list of strings,\n"
        "each being a concise statement of a key finding."
    )

    result = await agenerate_json(role="head", prompt=prompt)
    if result and isinstance(result, dict) and "findings" in result:
        return [str(f) for f in result["findings"] if isinstance(f, str)]

    # Fallback findings
    return [
        f"This survey provides a comprehensive overview of {broad_topic}.",
        f"Multiple research directions within {broad_topic} were identified and compared.",
        "Key methodologies and approaches were analyzed across sub-areas.",
    ]


async def run_survey(
    broad_topic: str,
    registry: dict[str, BaseToolAdapter],
    num_topics: int = 5,
) -> SurveyResult:
    """Run a complete survey generation pipeline.

    This is the main entry point for the Multi-Paper Survey Generator.
    It decomposes a broad topic, researches each sub-topic, and synthesizes
    a comprehensive survey paper with taxonomy, timeline, and comparisons.

    Args:
        broad_topic: The broad research area to survey.
        registry: Tool registry for web/paper searches.
        num_topics: Number of sub-topics to generate (3-8).

    Returns:
        SurveyResult with the generated survey and metadata.
    """
    start_time = time.time()
    run_id = f"survey-{uuid.uuid4().hex[:8]}"
    warnings: list[str] = []

    await apublish_progress(
        agent="Survey Orchestrator",
        status="running",
        detail=f"Starting survey on: {broad_topic}",
        message=f"Initiating survey generation",
    )

    # Step 1: Plan sub-topics
    topics = await plan_survey_topics(broad_topic, num_topics=num_topics)
    logger.info("Survey planned %d sub-topics for '%s'", len(topics), broad_topic)

    # Step 2: Research each topic
    topics = await research_survey_topics(topics, registry)

    # Collect warnings
    for topic in topics:
        for provider_data in topic.findings.values():
            if isinstance(provider_data, dict):
                for w in provider_data.get("warnings", []):
                    if isinstance(w, str):
                        warnings.append(f"{topic.name}: {w}")

    # Step 3: Generate summaries
    topics = await generate_summaries(topics)

    # Step 4: Identify cross-cutting themes
    key_findings = await identify_cross_cutting_themes(topics, broad_topic)

    # Step 5: Generate survey paper
    survey_markdown = generate_survey_paper(
        broad_topic=broad_topic,
        topics=topics,
        key_findings=key_findings,
    )

    # Step 6: Generate supplementary content
    taxonomy_table = generate_taxonomy_table(topics)
    timeline = generate_timeline(topics)
    research_landscape = generate_research_landscape(topics)

    # Step 7: Collect all papers
    all_papers = []
    seen_titles: set[str] = set()
    for topic in topics:
        for paper in topic.key_papers:
            title = paper.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_papers.append(paper)

    duration = time.time() - start_time

    await apublish_progress(
        agent="Survey Orchestrator",
        status="complete",
        detail=f"Survey complete: {len(all_papers)} papers across {len(topics)} topics",
        message="Survey generation complete",
    )

    return SurveyResult(
        run_id=run_id,
        topic=broad_topic,
        sub_topics=topics,
        survey_markdown=survey_markdown,
        taxonomy_table=taxonomy_table,
        timeline=timeline,
        research_landscape=research_landscape,
        key_findings=key_findings,
        paper_count=len(all_papers),
        duration_seconds=round(duration, 1),
        warnings=warnings,
    )
