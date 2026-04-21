from __future__ import annotations

import os
import re

from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.output.latex import build_bibtex, render_main_tex, escape_latex


def _build_body(state: GraphState) -> str:
    # v2.1: Pre-build URL -> CitationKey map for O(1) lookup
    url_to_citekey = {
        cit.get("url"): cit["key"]
        for cit in state["citations"]
        if cit.get("url")
    }

    sections: list[str] = []
    for section in state["combined_sections"]:
        heading = escape_latex(section.get("heading", "Section"))
        content = section.get("content", "No synthesized content available.")

        # Use the citation_map from the section
        citation_map = section.get("citation_map", {})

        # Replace [REF1], [REF2], etc. with proper cite keys
        ref_matches = re.findall(r"\[REF(\d+)\]", content)
        for ref_num in ref_matches:
            ref_key = f"REF{ref_num}"
            source_info = citation_map.get(ref_key)
            
            if source_info:
                source_url = source_info.get("url")
                found_key = url_to_citekey.get(source_url)
                
                if found_key:
                    content = content.replace(f"[{ref_key}]", f"\\cite{{{found_key}}}")
                else:
                    # Partial match or fallback to title
                    source_title = source_info.get("title", "")
                    for cit in state["citations"]:
                        if source_title in cit.get("title", ""):
                            content = content.replace(f"[{ref_key}]", f"\\cite{{{cit['key']}}}")
                            break
            
            # Final fallback if still present
            content = content.replace(f"[{ref_key}]", f"[{ref_num}]")

        sections.append(f"\\section{{{heading}}}\n{content}")

    if not sections:
        sections.append("\\section{Findings}\nNo evidence-backed findings were generated.")
    return "\n\n".join(sections)


def _build_subagent_prompt(state: GraphState, fallback_body: str) -> str:
    section_lines = []
    for section in state["combined_sections"]:
        heading = section.get("heading", "Section")
        content = section.get("content", "")
        section_lines.append(f"### {heading}\n{content}")

    citations = []
    for citation in state["citations"][:12]:
        key = citation.get("key", "ref")
        title = citation.get("title", "Untitled")
        citations.append(f"- {key}: {title}")

    section_block = "\n\n".join(section_lines) if section_lines else "No sections available."
    citation_block = "\n".join(citations) if citations else "No citations available."

    return (
        "You are an expert academic researcher writing a high-quality research paper for an IEEE/ACM conference. "
        "Your task is to transform the provided synthesized section content into a cohesive, professional LaTeX document body.\n\n"
        "### OBJECTIVES:\n"
        "1.  **Academic Tone**: Use a formal, objective, and precise academic tone throughout.\n"
        "2.  **Paper Structure**: Ensure the document flows logically. Organize the content into standard sections: Introduction (Background/Motivation), Related Work, Methodology (if applicable), Results/Findings, and Conclusion.\n"
        "3.  **Citation Integration**: You MUST use the available \\cite{key} commands for all claims. Do NOT invent keys; only use those provided in the 'Available Citations' list.\n"
        "4.  **LaTeX Syntax**: Return ONLY the LaTeX body content (from the first \\section to the last paragraph). No preamble, no \\begin{document}, and no markdown code blocks.\n\n"
        f"**TOPIC**: {state['topic']}\n\n"
        "**SYNTHESIZED SECTIONS (Draft Content)**:\n"
        f"{section_block}\n\n"
        "**AVAILABLE CITATIONS (Use these keys)**:\n"
        f"{citation_block}\n\n"
        "**DRAFT LATEX TO REFINE**:\n"
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

    # STREAMING FEEDBACK: If we haven't streamed chunks yet (local generation), 
    # we simulate it here so the UI feels alive.
    from research_agent.models.llm_client import _STREAM_CALLBACK
    chunk_handler = _STREAM_CALLBACK.get()
    if chunk_handler:
        # Stream the full content in small bursts
        chunk_size = 500
        for i in range(0, len(main_tex), chunk_size):
            chunk = main_tex[i : i + chunk_size]
            import asyncio
            if asyncio.iscoroutinefunction(chunk_handler):
                await chunk_handler(chunk)
            else:
                chunk_handler(chunk)
            # Small delay to make it look like "writing"
            await asyncio.sleep(0.02)

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
