from __future__ import annotations

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


def composer_node(state: GraphState) -> dict:
    avg_confidence = 0.0
    if state["section_confidence"]:
        avg_confidence = sum(state["section_confidence"].values()) / len(state["section_confidence"])

    abstract = (
        f"This document summarizes autonomous multi-agent research for '{state['topic']}'. "
        f"Average section confidence is {avg_confidence:.2f}."
    )

    main_tex = render_main_tex(
        template_name=state["template"],
        title=f"Research Synthesis: {state['topic']}",
        author_block="Research Agent",
        abstract=abstract,
        body=_build_body(state),
    )

    bibtex = build_bibtex(state["citations"])

    return {
        "latex_main": main_tex,
        "bibtex": bibtex,
        "phase": "latex_composed",
    }
