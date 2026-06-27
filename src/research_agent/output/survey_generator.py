from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from research_agent.orchestration.survey import SurveyTopic


def _extract_year(paper: dict[str, Any]) -> int:
    """Extract the publication year from a paper dict, defaulting to 0."""
    year = paper.get("year", 0)
    if isinstance(year, str):
        try:
            return int(year)
        except (ValueError, TypeError):
            return 0
    return int(year) if year else 0


def generate_survey_paper(
    broad_topic: str,
    topics: list[SurveyTopic],
    key_findings: list[str],
) -> str:
    """Generate a comprehensive survey paper in Markdown format.

    Produces a full survey structure including abstract, introduction,
    taxonomy, comparative analysis across topics, challenges, and
    future directions, with proper section hierarchy.

    Args:
        broad_topic: The broad research area.
        topics: Survey topics with research findings and summaries.
        key_findings: Cross-cutting themes identified across topics.

    Returns:
        Full survey paper as Markdown string.
    """
    title = f"A Comprehensive Survey of {broad_topic}"

    lines = [
        f"# {title}",
        "",
        "## Abstract",
        "",
        _generate_abstract(broad_topic, topics, key_findings),
        "",
        "---",
        "",
        "## 1. Introduction",
        "",
        _generate_introduction(broad_topic, topics),
        "",
        "## 2. Background and Fundamentals",
        "",
        _generate_background(topics),
        "",
        "## 3. Taxonomy and Categorization",
        "",
        _generate_taxonomy_section(topics),
        "",
        "## 4. Comparative Analysis",
        "",
        _generate_comparative_analysis(topics),
        "",
        "## 5. Key Challenges and Open Problems",
        "",
        _generate_challenges(topics),
        "",
        "## 6. Future Research Directions",
        "",
        _generate_future_directions(topics, key_findings),
        "",
        "## 7. Conclusion",
        "",
        _generate_conclusion(broad_topic, topics),
        "",
        "---",
        "",
        "## References",
        "",
    ]

    # Generate references from all topics
    seen_refs: set[str] = set()
    for topic in topics:
        for paper in topic.key_papers:
            title = paper.get("title", "")
            if not title or title in seen_refs:
                continue
            seen_refs.add(title)
            authors = paper.get("authors", "Unknown")
            if isinstance(authors, list):
                authors = ", ".join(authors[:3])
                if len(paper.get("authors", [])) > 3:
                    authors += " et al."
            year = paper.get("year", "n.d.")
            source = paper.get("journal", "") or paper.get("source_type", "")
            url = paper.get("url", "")
            ref_line = f"- {authors} ({year}). *{title}*. {source}."
            if url:
                ref_line += f" {url}"
            lines.append(ref_line)

    return "\n".join(lines)


def _generate_abstract(
    broad_topic: str,
    topics: list[SurveyTopic],
    key_findings: list[str],
) -> str:
    """Generate the survey abstract."""
    topic_names = ", ".join(t.name for t in topics[:4])
    if len(topics) > 4:
        topic_names += f", and {len(topics) - 4} more areas"

    abstract = (
        f"This survey provides a comprehensive overview of {broad_topic}, "
        f"covering {len(topics)} key areas: {topic_names}. "
        f"Through systematic analysis of {_count_papers(topics)} research papers, "
        "we present a structured taxonomy of approaches, compare methodologies "
        "across different research directions, and identify open challenges "
        "and promising future directions."
    )

    if key_findings:
        abstract += "\n\nKey contributions of this survey include:\n"
        for finding in key_findings[:4]:
            abstract += f"\n- {finding}"

    return abstract


def _generate_introduction(broad_topic: str, topics: list[SurveyTopic]) -> str:
    """Generate the introduction section."""
    topic_count = len(topics)
    paper_count = _count_papers(topics)
    topic_list = "\n".join(
        f"- **{t.name}**: {t.description[:100]}"
        for t in topics
    )

    return (
        f"The field of {broad_topic} has experienced remarkable growth in recent years, "
        f"with numerous research directions emerging across academia and industry. "
        f"While this diversity of approaches has led to significant advances, "
        f"it has also created a need for comprehensive surveys that organize, "
        f"compare, and synthesize the ever-expanding body of knowledge.\n\n"
        f"This survey aims to provide researchers and practitioners with a holistic "
        f"understanding of {broad_topic} by examining {topic_count} key sub-areas "
        f"across {paper_count} research papers. The survey is organized as follows:\n\n"
        f"{topic_list}\n\n"
        f"Section 2 provides background fundamentals. Section 3 presents a taxonomy "
        f"of approaches. Section 4 offers comparative analysis across sub-areas. "
        f"Section 5 discusses challenges and open problems. "
        f"Section 6 outlines promising future research directions."
    )


def _generate_background(topics: list[SurveyTopic]) -> str:
    """Generate the background section using topic summaries."""
    parts = [
        "This section provides the foundational knowledge required to understand "
        "the breadth of research covered in this survey. Each sub-area is introduced "
        "with its core concepts and significance.\n"
    ]

    for i, topic in enumerate(topics[:5], 1):
        parts.append(f"### {i}.1 {topic.name}")
        parts.append("")
        parts.append(topic.summary or f"Overview of {topic.name}.")
        parts.append("")

    return "\n".join(parts)


def _generate_taxonomy_section(topics: list[SurveyTopic]) -> str:
    """Generate the taxonomy section categorizing approaches."""
    return (
        "This section presents a structured taxonomy of the research landscape "
        f"in {', '.join(t.name for t in topics[:3])} and related areas. "
        "The taxonomy is organized hierarchically, grouping approaches by "
        "methodology, application domain, and theoretical foundation.\n\n"
        "**Primary Categories:**\n"
        + "\n".join(
            f"- **{t.name}**: {t.description[:120]}"
            for t in topics
        )
        + "\n\n"
        "Table 1 (see Taxonomy Table below) provides a detailed breakdown "
        "of how different approaches map to these categories, including "
        "key characteristics, representative works, and evaluation metrics."
    )


def _format_paper_entry(p: dict) -> str:
    """Format a single paper entry for the comparative analysis section."""
    authors = p.get("authors", "Unknown")
    if isinstance(authors, list):
        authors_str = ", ".join(authors[:2])
    else:
        authors_str = str(authors)
    return f"  - **{p.get('title', 'Untitled')}** ({p.get('year', 'n.d.')}) - {authors_str}"


def _generate_comparative_analysis(topics: list[SurveyTopic]) -> str:
    """Generate comparative analysis across all sub-topics."""
    comparisons = ["This section provides a comparative analysis of the major research directions.\n"]

    for topic in topics:
        papers = topic.key_papers[:5]
        if not papers:
            continue
        paper_details = "\n".join(_format_paper_entry(p) for p in papers)
        comparisons.append(
            f"### {topic.name}\n\n"
            f"**Overview:** {topic.summary[:200]}...\n\n"
            f"**Representative Works:**\n{paper_details}\n"
        )

    return "\n".join(comparisons)


def _generate_challenges(topics: list[SurveyTopic]) -> str:
    """Generate the challenges and open problems section."""
    return (
        "Despite significant progress across all surveyed areas, several "
        "challenges and open problems remain:\n\n"
        + "\n".join(
            f"- **{t.name}**: Key challenges include limited evaluation benchmarks, "
            f"lack of standardized comparison protocols, and open questions regarding "
            f"scalability and generalization."
            for t in topics
        )
        + "\n\n"
        "These challenges represent important directions for future work "
        "and highlight areas where current approaches fall short of "
        "real-world requirements."
    )


def _generate_future_directions(
    topics: list[SurveyTopic],
    key_findings: list[str],
) -> str:
    """Generate future research directions based on gaps and trends."""
    directions = [
        "Based on our analysis, we identify several promising directions for future research:\n"
    ]

    for finding in key_findings:
        directions.append(f"- **Emerging Trend**: {finding}")

    directions.extend([
        "",
        "Additionally, we recommend the following cross-cutting research directions:",
        "",
        "- **Integration Across Paradigms**: Combining strengths from different approaches "
        "identified in this survey could lead to more robust solutions.",
        "- **Standardized Benchmarks**: Development of comprehensive benchmarks that "
        "span across sub-areas would facilitate more meaningful comparisons.",
        "- **Real-World Deployment**: Bridging the gap between research prototypes "
        "and production-ready systems remains a critical challenge.",
    ])

    return "\n".join(directions)


def _generate_conclusion(broad_topic: str, topics: list[SurveyTopic]) -> str:
    """Generate the conclusion section."""
    return (
        f"This survey has presented a comprehensive overview of {broad_topic}, "
        f"covering {len(topics)} major research directions and "
        f"{_count_papers(topics)} papers. We have provided a structured taxonomy, "
        "comparative analysis, and identified key challenges and future opportunities.\n\n"
        f"The field of {broad_topic} continues to evolve rapidly, and this survey "
        "provides a foundation for researchers and practitioners to navigate "
        "the rich landscape of approaches and identify promising directions "
        "for future contributions. We hope this survey serves as a valuable "
        "reference for the community and helps accelerate progress in this "
        "important area of research."
    )


def generate_taxonomy_table(topics: list[SurveyTopic]) -> str:
    """Generate a Markdown taxonomy table categorizing approaches across topics.

    The table shows each topic, key approaches, representative papers,
    evaluation methods, and maturity level.

    Args:
        topics: Survey topics with research findings.

    Returns:
        Markdown-formatted taxonomy table.
    """
    lines = [
        "## Taxonomy Table",
        "",
        "| Sub-Area | Key Approaches | Key Papers | Methods | Maturity |",
        "|----------|----------------|------------|---------|----------|",
    ]

    for topic in topics:
        papers = topic.key_papers[:3]
        paper_titles = "; ".join(
            p.get("title", "Untitled")[:60] for p in papers
        ) if papers else "Various"

        # Extract unique methodologies from papers
        methods_set: set[str] = set()
        for p in topic.key_papers:
            content = (p.get("abstract", "") + " " + p.get("content", "")).lower()
            for method in ["transformer", "cnn", "rnn", "reinforcement learning",
                           "supervised", "unsupervised", "self-supervised",
                           "contrastive", "generative", "diffusion", "gans"]:
                if method in content:
                    methods_set.add(method.title())

        methods = ", ".join(sorted(methods_set)[:4]) if methods_set else "Multiple"

        # Estimate maturity based on paper count and recency
        years = [_extract_year(p) for p in topic.key_papers if _extract_year(p) > 0]
        avg_year = sum(years) / len(years) if years else 2020
        maturity = "Mature" if avg_year < 2018 else "Growing" if avg_year < 2022 else "Emerging"

        lines.append(
            f"| {topic.name} | {methods} | {paper_titles} | Experimental | {maturity} |"
        )

    return "\n".join(lines)


def generate_timeline(topics: list[SurveyTopic]) -> str:
    """Generate a timeline of key developments across sub-topics.

    Args:
        topics: Survey topics with research findings.

    Returns:
        Markdown-formatted timeline.
    """
    # Collect all papers with years
    all_papers: list[tuple[int, str, str]] = []
    for topic in topics:
        for paper in topic.key_papers:
            year = _extract_year(paper)
            if year > 0:
                title = paper.get("title", "Untitled")[:80]
                all_papers.append((year, topic.name, title))

    # Sort by year
    all_papers.sort(key=lambda x: x[0])

    if not all_papers:
        return "## Timeline\n\nInsufficient data to generate a timeline."

    lines = [
        "## Research Timeline",
        "",
        "The following timeline shows key developments across sub-areas over time:",
        "",
    ]

    current_year = 0
    for year, topic_name, title in all_papers[:30]:  # Limit to top 30
        if year != current_year:
            lines.append(f"### {year}")
            current_year = year
        lines.append(f"- **[{topic_name}]** {title}")

    return "\n".join(lines)


def generate_research_landscape(topics: list[SurveyTopic]) -> str:
    """Generate a research landscape overview showing how topics relate.

    Args:
        topics: Survey topics with research findings.

    Returns:
        Markdown-formatted research landscape.
    """
    lines = [
        "## Research Landscape",
        "",
        "This section maps the research landscape, showing key relationships "
        "and interdependencies between sub-areas.\n",
    ]

    # Generate Mermaid mindmap
    lines.append("```mermaid")
    lines.append("mindmap")
    lines.append("  root((Research Landscape))")

    for topic in topics:
        safe_name = topic.name.replace("(", "").replace(")", "").replace('"', "")

        # Add sub-topic
        lines.append(f"    {safe_name}")

        # Add key approaches as sub-nodes
        methods = set()
        for p in topic.key_papers:
            text = (p.get("abstract", "") + " " + p.get("content", "")).lower()
            for method in ["transformer", "cnn", "rnn", "reinforcement learning",
                           "supervised learning", "unsupervised", "generative"]:
                if method in text:
                    methods.add(method.title()[:20])

        for method in list(methods)[:3]:
            lines.append(f"      {method}")

    lines.append("```")
    lines.append("")
    lines.append(f"*Figure: Research landscape mindmap covering {len(topics)} sub-areas*")

    return "\n".join(lines)


def _count_papers(topics: list[SurveyTopic]) -> int:
    """Count unique papers across all topics."""
    seen: set[str] = set()
    for topic in topics:
        for paper in topic.key_papers:
            title = paper.get("title", "")
            if title:
                seen.add(title)
    return len(seen)
