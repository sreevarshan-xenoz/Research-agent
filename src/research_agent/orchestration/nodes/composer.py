from __future__ import annotations

import os
import re

from research_agent.models import agenerate_text, agenerate_json
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.output.latex.renderer import render_main_tex, build_bibtex, escape_latex
from research_agent.config import load_settings


async def composer_node(state: GraphState) -> dict:
    await apublish_progress(
        agent="Composer",
        status="running",
        detail="Synthesizing final document",
        message="Generating LaTeX output",
    )

    # 1. Build a fallback body from combined_sections
    fallback_body = _build_body(state)
    run_warnings = []

    # 2. Attempt to use LLM to refine the body and metadata (Title, Abstract)
    language = state.get("language", "en")
    language_map = {
        "en": "English",
        "de": "German (Deutsch)",
        "fr": "French (Français)",
        "es": "Spanish (Español)",
        "it": "Italian (Italiano)",
    }
    lang_name = language_map.get(language, "English")

    prompt = (
        f"You are a scientific technical writer. Your task is to compose a final academic research paper in {lang_name}.\n\n"
        "Input Data:\n"
        f"Topic: {state['topic']}\n"
        f"Draft Sections (in various languages/raw data):\n{fallback_body}\n\n"
        "Instructions:\n"
        f"1. Translate and refine all content into high-quality {lang_name}.\n"
        f"2. Generate a compelling Title and Abstract in {lang_name}.\n"
        "3. Ensure the tone is academic and formal.\n"
        "4. Output exactly one JSON object with these keys: 'title', 'abstract', 'body' (LaTeX content without preamble).\n"
    )

    composed_json = await agenerate_json(
        role="orchestrator",
        prompt=prompt,
        temperature=0.2
    )

    if not composed_json or not isinstance(composed_json, dict):
        # Fallback
        title = state["topic"]
        abstract = "Research abstract."
        body = fallback_body
    else:
        title = composed_json.get("title", state["topic"])
        abstract = composed_json.get("abstract", "Research abstract.")
        body = composed_json.get("body", fallback_body)

    # Use render_main_tex with the language from state
    main_tex = render_main_tex(
        template_name=state["template"],
        title=title,
        author_block="Research Agent (Autonomous)",
        abstract=abstract,
        body=body,
        language=language
    )

    # 3. Build BibTeX
    bibtex = build_bibtex(state["citations"])

    await apublish_progress(
        agent="Composer",
        status="complete",
        detail="LaTeX content generated",
        message="Composer complete",
    )
    return {
        "latex_main": main_tex,
        "bibtex": bibtex,
        "run_warnings": run_warnings,
        "phase": "latex_composed",
    }


def _build_body(state: GraphState) -> str:
    sections = []
    combined = state.get("combined_sections", [])
    
    for sec in combined:
        heading = str(sec.get("heading", "Section")).strip()
        content = str(sec.get("content", "")).strip()
        if heading and content:
            sections.append(f"\\section{{{heading}}}\n{content}")

    if not sections:
        sections.append("\\section{Findings}\nNo evidence-backed findings were generated.")
    
    # v2: Append generated figures
    figures = state.get("figures", [])
    for fig in figures:
        if fig.get("type") == "tikz" and fig.get("content"):
            tikz_content = fig["content"]
            caption = escape_latex(fig.get("caption", "System Diagram"))
            
            # Use figure* for two-column templates if it looks complex, or stick to figure
            fig_env = "figure"
            if "2col" in state.get("template", ""):
                fig_env = "figure*" # Span both columns
            
            sections.append(
                f"\\begin{{{fig_env}}}[htbp]\n"
                "\\centering\n"
                f"{tikz_content}\n"
                f"\\caption{{{caption}}}\n"
                f"\\end{{{fig_env}}}"
            )

    return "\n\n".join(sections)


def _build_subagent_prompt(state: GraphState, fallback_body: str) -> str:
    section_lines = []
    for sec in state.get("combined_sections", []):
        section_lines.append(f"### {sec.get('heading')}\n{sec.get('content')}")
    
    sections_text = "\n\n".join(section_lines)
    
    return (
        "You are a scientific technical writer. Your task is to refine and organize research findings into a professional LaTeX document body.\n\n"
        f"Topic: {state['topic']}\n"
        f"Research Sections:\n{sections_text}\n\n"
        "Guidelines:\n"
        "1. Maintain a formal academic tone.\n"
        "2. Ensure smooth transitions between sections.\n"
        "3. Preserve all citations in the format [Source Key].\n"
        "4. DO NOT include the preamble or document environment (\begin{document}).\n"
        "5. Output the LaTeX body directly."
    )
