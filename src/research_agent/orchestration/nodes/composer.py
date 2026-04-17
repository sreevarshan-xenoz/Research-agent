from __future__ import annotations

import os

from research_agent.config import load_settings
from research_agent.models import generate_with_nvidia
from research_agent.orchestration.state import GraphState
from research_agent.output.latex import build_bibtex, render_main_tex


def _build_body(state: GraphState) -> str:
    citation_keys = [citation["key"] for citation in state["citations"][:8] if "key" in citation]
    citation_clause = ""
    if citation_keys:
        joined = ",".join(citation_keys)
        citation_clause = f"\\nSupporting references: \\cite{{{joined}}}."

    sections: list[str] = []
    for section in state["combined_sections"]:
        heading = section.get("heading", "Section")
        content = section.get("content", "No synthesized content available.")
        sections.append(f"\\section{{{heading}}}\\n{content}{citation_clause}")

    if not sections:
        sections.append("\\section{Findings}\\nNo evidence-backed findings were generated.")
    return "\\n\\n".join(sections)


def _use_nvidia_model() -> bool:
    value = os.getenv("ENABLE_NVIDIA_MODEL", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _build_nvidia_prompt(state: GraphState, fallback_body: str) -> str:
    section_lines = []
    for section in state["combined_sections"]:
        heading = section.get("heading", "Section")
        content = section.get("content", "")
        section_lines.append(f"- {heading}: {content}")

    citations = []
    for citation in state["citations"][:12]:
        key = citation.get("key", "ref")
        title = citation.get("title", "Untitled")
        citations.append(f"- {key}: {title}")

    section_block = "\n".join(section_lines) if section_lines else "- no sections"
    citation_block = "\n".join(citations) if citations else "- no citations"

    return (
        "You are writing the LaTeX body content for a research paper. "
        "Return only valid LaTeX body sections (no preamble, no documentclass, no markdown).\n\n"
        f"Topic: {state['topic']}\n\n"
        "Combined section evidence:\n"
        f"{section_block}\n\n"
        "Available citations:\n"
        f"{citation_block}\n\n"
        "Fallback draft body to improve:\n"
        f"{fallback_body}\n"
    )


def composer_node(state: GraphState) -> dict:
    avg_confidence = 0.0
    if state["section_confidence"]:
        avg_confidence = sum(state["section_confidence"].values()) / len(state["section_confidence"])

    abstract = (
        f"This document summarizes autonomous multi-agent research for '{state['topic']}'. "
        f"Average section confidence is {avg_confidence:.2f}."
    )

    body = _build_body(state)
    run_warnings = list(state["run_warnings"])

    if _use_nvidia_model():
        settings = load_settings()
        model_name = os.getenv("NVIDIA_MODEL") or settings.models.strong_model
        nvidia_text = generate_with_nvidia(
            model=model_name,
            prompt=_build_nvidia_prompt(state, body),
            temperature=0.7,
            top_p=0.8,
            max_tokens=4096,
        )
        if nvidia_text:
            body = nvidia_text
        else:
            run_warnings.append("nvidia_generation:fallback_to_local_composer")

    main_tex = render_main_tex(
        template_name=state["template"],
        title=f"Research Synthesis: {state['topic']}",
        author_block="Research Agent",
        abstract=abstract,
        body=body,
    )

    bibtex = build_bibtex(state["citations"])

    return {
        "latex_main": main_tex,
        "bibtex": bibtex,
        "run_warnings": run_warnings,
        "phase": "latex_composed",
    }
