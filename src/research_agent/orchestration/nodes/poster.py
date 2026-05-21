from __future__ import annotations

from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.output.latex.renderer import render_poster_tex


async def poster_generator_node(state: GraphState) -> dict:
    """Generates an Academic Poster .tex content."""
    await apublish_progress(
        agent="Poster Gen",
        status="running",
        detail="Creating A0 poster",
        message="Generating academic poster",
    )
    
    sections = state.get("combined_sections", [])
    if not sections:
        return {"phase": "poster_skipped"}

    poster_tex = render_poster_tex(
        topic=state["topic"],
        sections=sections
    )

    await apublish_progress(
        agent="Poster Gen",
        status="complete",
        detail="Poster generated",
        message="Academic poster ready",
    )
    
    return {
        "poster_tex": poster_tex,
        "phase": "poster_generated"
    }
