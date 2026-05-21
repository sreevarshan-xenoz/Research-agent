from __future__ import annotations

from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.output.latex.renderer import render_beamer_tex


async def presentation_generator_node(state: GraphState) -> dict:
    """Generates a Beamer presentation .tex content based on synthesized sections."""
    await apublish_progress(
        agent="Presentation Gen",
        status="running",
        detail="Creating Beamer slides",
        message="Generating academic presentation deck",
    )
    
    sections = state.get("combined_sections", [])
    if not sections:
        return {"phase": "presentation_skipped"}

    presentation_tex = render_beamer_tex(
        topic=state["topic"],
        sections=sections
    )

    await apublish_progress(
        agent="Presentation Gen",
        status="complete",
        detail="Slides generated",
        message="Presentation deck ready",
    )
    
    return {
        "presentation_tex": presentation_tex,
        "phase": "presentation_generated"
    }
