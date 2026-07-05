"""Automated Peer Review with Confidence Scoring (P37).

Replaces the simple single-pass peer review with a structured multi-persona
review system that:
1. Runs 3 simulated reviewer personas (theoretical, applied, experimental)
2. Scores each paper section for confidence (0.0-1.0)
3. Generates structured reviews with strengths, weaknesses, and questions
4. Aggregates all reviews into a meta-review with consensus scoring
"""

from __future__ import annotations

import json
import logging
from typing import Any

from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.peer_review.models import (
    PersonaReview,
    ReviewCriterion,
    ReviewSection,
    persona_review_to_dict,
    meta_review_to_dict,
)
from research_agent.peer_review.personas import ALL_PERSONAS
from research_agent.peer_review.scorer import score_paper_sections
from research_agent.peer_review.aggregator import aggregate_reviews


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Review section template
# ---------------------------------------------------------------------------

_SECTION_EVALUATION_TEMPLATE = """
Section: "{section_name}"

Content:
{section_content}

Evaluate this section on the following criteria (score 0.0-1.0):
1. Clarity: Is the writing clear, well-structured, and easy to follow?
2. Evidence: Are claims supported by citations or data?
3. Methodology: Is the approach well-described and justified?
4. Rigor: Is the analysis thorough and technically sound?

For each criterion, provide:
- A score (0.0-1.0)
- A brief justification (1-2 sentences)

Also identify:
- Strengths: What does this section do well?
- Weaknesses: What could be improved?
- Suggestions: Specific actionable recommendations
"""


# ---------------------------------------------------------------------------
# Full review prompt builder
# ---------------------------------------------------------------------------


def _build_persona_prompt(
    persona_name: str,
    persona_label: str,
    rubric: str,
    focus_areas: list[str],
    topic: str,
    latex_main: str,
    combined_sections: list[dict[str, Any]],
) -> str:
    """Build the full LLM prompt for a single persona review."""
    focus_bullets = "\n".join(f"- {area}" for area in focus_areas)

    # Build section summaries for the reviewer to reference
    section_overview = ""
    for i, sec in enumerate(combined_sections):
        title = sec.get("title", f"Section {i+1}")
        content = sec.get("content") or sec.get("text") or sec.get("latex") or ""
        snippet = content[:500] if content else "(no content)"
        section_overview += f"\n### {title}\n{snippet}\n"

    prompt = (
        f"You are acting as the **{persona_label}** — a peer reviewer for academic papers.\n\n"
        f"## Your Persona\n{rubric}\n\n"
        f"## Your Focus Areas\n{focus_bullets}\n\n"
        f"## Paper Topic\n{topic}\n\n"
        f"## Full LaTeX Draft\n```latex\n{latex_main[:8000]}\n```\n\n"
        f"## Section Overviews\n{section_overview}\n\n"
        f"## Review Instructions\n\n"
        f"Write a structured peer review in JSON format with the following schema:\n"
        f"```json\n"
        f"{{\n"
        f'  "overall_score": 0.0-1.0,\n'
        f'  "overall_confidence": 0.0-1.0,\n'
        f'  "recommendation": "accept" | "minor-revision" | "major-revision" | "reject",\n'
        f'  "sections": [\n'
        f"    {{\n"
        f'      "section_name": "Introduction",\n'
        f'      "overall_score": 0.0-1.0,\n'
        f'      "criteria": [\n'
        f'        {{"name": "Clarity", "score": 0.0-1.0, "justification": "..."}},\n'
        f'        {{"name": "Evidence", "score": 0.0-1.0, "justification": "..."}},\n'
        f'        {{"name": "Methodology", "score": 0.0-1.0, "justification": "..."}},\n'
        f'        {{"name": "Rigor", "score": 0.0-1.0, "justification": "..."}}\n'
        f"      ],\n"
        f'      "strengths": ["..."],\n'
        f'      "weaknesses": ["..."],\n'
        f'      "suggestions": ["..."]\n'
        f"    }}\n"
        f"  ],\n"
        f'  "strengths": ["Overall paper strength 1", "Strength 2"],\n'
        f'  "weaknesses": ["Overall weakness 1", "Weakness 2"],\n'
        f'  "questions": ["Question for authors 1", "Question 2"]\n'
        f"}}\n"
        f"```\n\n"
        f"Focus on your persona's unique perspective. Be specific, cite evidence from "
        f"the paper, and provide actionable feedback. Output ONLY valid JSON, no markdown "
        f"wrapping or additional text."
    )
    return prompt


# ---------------------------------------------------------------------------
# Review section parsing helpers
# ---------------------------------------------------------------------------


def _parse_section_from_dict(
    section_data: dict[str, Any],
    section_name: str,
) -> ReviewSection:
    """Parse a ReviewSection from a dict returned by the LLM."""
    criteria = []
    for c in section_data.get("criteria", []):
        criteria.append(ReviewCriterion(
            name=c.get("name", "Unnamed"),
            score=float(c.get("score", 0.5)),
            justification=c.get("justification", ""),
        ))
    return ReviewSection(
        section_name=section_name,
        overall_score=float(section_data.get("overall_score", 0.5)),
        criteria=criteria,
        strengths=section_data.get("strengths", []),
        weaknesses=section_data.get("weaknesses", []),
        suggestions=section_data.get("suggestions", []),
    )


def _parse_persona_review(
    persona_name: str,
    persona_label: str,
    raw_json: dict[str, Any] | None,
    raw_text: str,
) -> PersonaReview:
    """Parse an LLM response into a structured PersonaReview.

    Falls back gracefully if the JSON is incomplete or malformed.
    """
    if raw_json is None:
        return PersonaReview(
            persona=persona_name,
            persona_label=persona_label,
            overall_score=0.5,
            overall_confidence=0.3,
            recommendation="major-revision",
            raw_text=raw_text,
        )

    sections_data = raw_json.get("sections", [])
    sections = [
        _parse_section_from_dict(s, s.get("section_name", f"Section {i+1}"))
        for i, s in enumerate(sections_data)
    ]

    return PersonaReview(
        persona=persona_name,
        persona_label=persona_label,
        overall_score=float(raw_json.get("overall_score", 0.5)),
        overall_confidence=float(raw_json.get("overall_confidence", 0.5)),
        sections=sections,
        strengths=raw_json.get("strengths", []),
        weaknesses=raw_json.get("weaknesses", []),
        questions=raw_json.get("questions", []),
        recommendation=raw_json.get("recommendation", "major-revision"),
        raw_text=raw_text,
    )


def _extract_json_from_text(text: str) -> dict[str, Any] | None:
    """Try to extract a JSON object from LLM text output."""
    text = text.strip()
    if not text:
        return None

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    if "```json" in text:
        json_part = text.split("```json", 1)[1].split("```", 1)[0].strip()
        try:
            return json.loads(json_part)
        except (json.JSONDecodeError, IndexError):
            pass

    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            try:
                return json.loads(parts[1].strip())
            except (json.JSONDecodeError, IndexError):
                pass

    # Try finding first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Persona review runner
# ---------------------------------------------------------------------------


async def _run_persona_review(
    persona_name: str,
    persona_label: str,
    rubric: str,
    focus_areas: list[str],
    topic: str,
    latex_main: str,
    combined_sections: list[dict[str, Any]],
    temperature: float,
) -> PersonaReview:
    """Run a single persona review and parse the result."""
    prompt = _build_persona_prompt(
        persona_name=persona_name,
        persona_label=persona_label,
        rubric=rubric,
        focus_areas=focus_areas,
        topic=topic,
        latex_main=latex_main,
        combined_sections=combined_sections,
    )

    raw_text = await agenerate_text(
        role="orchestrator",
        prompt=prompt,
        temperature=temperature,
        max_tokens=4096,
    )

    if not raw_text:
        logger.warning("Persona review returned no text for %s", persona_label)
        return PersonaReview(
            persona=persona_name,
            persona_label=persona_label,
            overall_score=0.5,
            overall_confidence=0.3,
            recommendation="major-revision",
            raw_text="",
        )

    raw_json = _extract_json_from_text(raw_text)
    if raw_json is None:
        logger.warning(
            "Could not parse JSON from persona review for %s. Using fallback.",
            persona_label,
        )

    return _parse_persona_review(
        persona_name=persona_name,
        persona_label=persona_label,
        raw_json=raw_json,
        raw_text=raw_text,
    )


# ---------------------------------------------------------------------------
# Main node function
# ---------------------------------------------------------------------------


async def peer_reviewer_node(state: GraphState) -> dict:
    """Run multi-persona peer review with confidence scoring.

    Each persona generates a structured review, sections are scored
    automatically, and results are aggregated into a meta-review.
    """
    await apublish_progress(
        agent="Peer Reviewer",
        status="running",
        detail="Starting multi-persona structured review",
        message="Running automated peer review (P37)",
    )

    latex_main = state.get("latex_main", "")
    combined_sections = state.get("combined_sections", [])
    topic = state.get("topic", "Untitled")

    if not latex_main:
        await apublish_progress(
            agent="Peer Reviewer",
            status="complete",
            detail="No LaTeX draft available",
            message="Peer review skipped",
        )
        return {"phase": "peer_review_skipped"}

    # -----------------------------------------------------------------------
    # Step 1: Automated section confidence scoring
    # -----------------------------------------------------------------------
    await apublish_progress(
        agent="Peer Reviewer",
        status="running",
        detail="Scoring section confidence",
        message="Analyzing section quality",
    )

    section_scores = score_paper_sections(combined_sections)

    # -----------------------------------------------------------------------
    # Step 2: Run multi-persona reviews
    # -----------------------------------------------------------------------
    persona_reviews: list[PersonaReview] = []

    for persona in ALL_PERSONAS:
        await apublish_progress(
            agent="Peer Reviewer",
            status="running",
            detail=f"Running {persona.short_label} review",
            message=f"Reviewing as {persona.short_label}",
        )

        review = await _run_persona_review(
            persona_name=persona.name,
            persona_label=persona.short_label,
            rubric=persona.rubric_description,
            focus_areas=persona.focus_areas,
            topic=topic,
            latex_main=latex_main,
            combined_sections=combined_sections,
            temperature=persona.temperature,
        )
        persona_reviews.append(review)

    # -----------------------------------------------------------------------
    # Step 3: Aggregate reviews into meta-review
    # -----------------------------------------------------------------------
    await apublish_progress(
        agent="Peer Reviewer",
        status="running",
        detail="Aggregating reviews into meta-review",
        message="Computing consensus",
    )

    meta_review = aggregate_reviews(persona_reviews)

    # -----------------------------------------------------------------------
    # Step 4: Build combined markdown report
    # -----------------------------------------------------------------------

    # Build the combined peer review report (human-readable markdown)
    report_parts: list[str] = [
        "# Automated Peer Review Report",
        "",
        f"**Topic:** {topic}",
        "",
        "---",
        "",
    ]

    # Meta-review summary
    report_parts.append(meta_review.meta_review_text)
    report_parts.append("")
    report_parts.append("---")
    report_parts.append("")

    # Individual persona reviews
    for i, review in enumerate(persona_reviews):
        report_parts.append(f"## {review.persona_label} Review")
        report_parts.append("")
        report_parts.append(
            f"**Overall Score:** {review.overall_score:.3f} | "
            f"**Confidence:** {review.overall_confidence:.3f} | "
            f"**Recommendation:** {review.recommendation}"
        )
        report_parts.append("")

        if review.strengths:
            report_parts.append("### Strengths")
            for s in review.strengths:
                report_parts.append(f"- {s}")
            report_parts.append("")

        if review.weaknesses:
            report_parts.append("### Weaknesses")
            for w in review.weaknesses:
                report_parts.append(f"- {w}")
            report_parts.append("")

        if review.questions:
            report_parts.append("### Questions")
            for q in review.questions:
                report_parts.append(f"- {q}")
            report_parts.append("")

        # Per-section breakdown
        if review.sections:
            report_parts.append("### Section Scores")
            report_parts.append("")
            report_parts.append("| Section | Score | Key Criteria |")
            report_parts.append("|---------|-------|-------------|")
            for sec in review.sections:
                criteria_summary = "; ".join(
                    f"{c.name}: {c.score:.2f}" for c in sec.criteria[:3]
                )
                report_parts.append(
                    f"| {sec.section_name} | {sec.overall_score:.2f} | {criteria_summary} |"
                )
            report_parts.append("")

        if i < len(persona_reviews) - 1:
            report_parts.append("---")
            report_parts.append("")

    # Automated section scores
    if section_scores:
        report_parts.append("## Automated Section Confidence Scores")
        report_parts.append("")
        report_parts.append("| Section | Confidence |")
        report_parts.append("|---------|-----------|")
        for sec_name, score in sorted(section_scores.items()):
            report_parts.append(f"| {sec_name} | {score:.3f} |")
        report_parts.append("")

    report = "\n".join(report_parts)

    # -----------------------------------------------------------------------
    # Step 5: Package state updates
    # -----------------------------------------------------------------------

    await apublish_progress(
        agent="Peer Reviewer",
        status="complete",
        detail="Peer review complete",
        message=f"{len(persona_reviews)} persona reviews aggregated",
    )

    return {
        "peer_review_report": report,
        "peer_reviews": [persona_review_to_dict(r) for r in persona_reviews],
        "peer_review_meta": meta_review_to_dict(meta_review),
        "peer_review_personas": [p.short_label for p in ALL_PERSONAS],
        "phase": "peer_review_complete",
    }
