from __future__ import annotations

import os
import re

from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.output.latex import build_bibtex, render_main_tex, escape_latex


def _build_body(state: GraphState) -> str:
    sections: list[str] = []
    for section in state["combined_sections"]:
        heading = escape_latex(section.get("heading", "Section"))
        content = section.get("content", "No synthesized content available.")

        # Use the citation_map from the section if available
        citation_map = section.get("citation_map", {})

        # Replace [REF1], [REF2], etc. with proper cite keys
        ref_matches = re.findall(r"\[REF(\d+)\]", content)
        for ref_num in ref_matches:
            idx = int(ref_num)
            ref_key = f"REF{idx}"

            # Get the source info from the citation_map
            source_info = citation_map.get(ref_key)
            if source_info:
                # Find a matching citation in state['citations']
                source_title = source_info.get("title", "")
                source_url = source_info.get("url", "")
                found_key = None
                for cit in state["citations"]:
                    cit_title = cit.get("title", "")
                    cit_url = cit.get("url", "")
                    if source_title in cit_title or source_url in cit_url:
                        found_key = cit["key"]
                        break

                if found_key:
                    content = content.replace(f"[REF{ref_num}]", f"\\cite{{{found_key}}}")
                else:
                    content = content.replace(f"[REF{ref_num}]", f"[{ref_num}] (source: {source_title})")
            else:
                # Fallback: find any available citation for this task_id
                task_id = section.get("task_id", "")
                found_key = None
                for cit in state["citations"]:
                    if cit["key"].startswith(f"{task_id}_"):
                        found_key = cit["key"]
                        break
                if found_key:
                    content = content.replace(f"[REF{ref_num}]", f"\\cite{{{found_key}}}")
                else:
                    content = content.replace(f"[REF{ref_num}]", f"[{ref_num}]")

        sections.append(f"\\section{{{heading}}}\n{content}")

    if not sections:
        sections.append("\\section{Findings}\nNo evidence-backed findings were generated.")
    return "\n\n".join(sections)


def _build_subagent_prompt(state: GraphState, fallback_body: str) -> str:
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
        "Draft body to improve (ensure all \\cite commands are preserved):\n"
        f"{fallback_body}\n"
    )


def _use_subagent_model() -> bool:
    """Check if a subagent model (cloud) is configured for composition."""
    # Check if subagent model is explicitly set
    subagent = os.getenv("SUBAGENT_MODEL", "").strip()
    if subagent:
        return True

    # Fall back to checking for OpenRouter or NVIDIA keys
    if os.getenv("OPENROUTER_API_KEY", "").strip():
        return True
    if os.getenv("NVIDIA_API_KEY", "").strip() or os.getenv("NVIDIA_NIMS_API_KEY", "").strip():
        return True

    return False


async def composer_node(state: GraphState) -> dict:
    from research_agent.config import load_settings
    settings = load_settings()
    
    await apublish_progress(
        agent="Composer",
        status="running",
        detail="Generating LaTeX output",
        message="Composing final document",
    )
    avg_confidence = 0.0
    if state["section_confidence"]:
        avg_confidence = sum(state["section_confidence"].values()) / len(state["section_confidence"])

    abstract = (
        f"This document summarizes autonomous multi-agent research for '{state['topic']}'. "
        f"Average section confidence is {avg_confidence:.2f}."
    )

    body = _build_body(state)
    run_warnings = list(state["run_warnings"])

    if _use_subagent_model():
        await apublish_progress(
            agent="Composer",
            status="running",
            detail="Generating content via cloud subagent",
            message="Using cloud model for LaTeX body",
        )
        subagent_text = await agenerate_text(
            role="subagent",
            prompt=_build_subagent_prompt(state, body),
            temperature=0.7,
            top_p=0.8,
            max_tokens=4096,
        )
        if subagent_text:
            body = subagent_text
        else:
            run_warnings.append("subagent_generation:fallback_to_local_composer")

    # Use render_main_tex with the language from settings
    main_tex = render_main_tex(
        template_name=state["template"],
        title=f"Research Synthesis: {state['topic']}",
        author_block="Research Agent",
        abstract=abstract,
        body=body,
        language=settings.output.language
    )

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
