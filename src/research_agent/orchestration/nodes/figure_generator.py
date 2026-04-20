from __future__ import annotations

import re
from typing import Any

from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


async def figure_generator_node(state: GraphState) -> dict:
    """Generates Mermaid diagram code based on research findings."""
    await apublish_progress(
        agent="Figure Generator",
        status="running",
        detail="Designing diagrams",
        message="Synthesizing visual representations",
    )
    
    sections = state.get("combined_sections", [])
    if not sections:
        return {"phase": "figures_skipped"}

    # Concatenate section headings and content for context
    context = "\n".join([
        f"Section: {s.get('heading')}\nContent: {s.get('content', '')[:500]}"
        for s in sections[:3]
    ])

    prompt = (
        "You are a technical illustrator. Create a Mermaid.js diagram that represents "
        "the core architecture, flow, or concepts described in the following research sections.\n\n"
        f"Topic: {state['topic']}\n\n"
        "Research Context:\n"
        f"{context}\n\n"
        "Instructions:\n"
        "1. Output ONLY the Mermaid code block starting with 'graph TD', 'sequenceDiagram', or 'classDiagram'.\n"
        "2. Do not use markdown code blocks (```mermaid).\n"
        "3. Ensure the diagram is clear and professional.\n"
        "4. If no diagram makes sense, return 'NO_DIAGRAM'.\n"
    )

    mermaid_code = await agenerate_text(
        role="orchestrator",
        prompt=prompt,
        temperature=0.2,
        max_tokens=1000
    )

    figures = []
    if mermaid_code:
        code_lower = mermaid_code.lower()
        if "graph" in code_lower or "diagram" in code_lower:
            # Clean up any potential markdown residue
            clean_code = mermaid_code.replace("```mermaid", "").replace("```", "").strip()
            if clean_code != "NO_DIAGRAM":
                figures.append({
                    "type": "mermaid",
                    "content": clean_code,
                    "caption": f"Conceptual diagram for {state['topic']}"
                })

    await apublish_progress(
        agent="Figure Generator",
        status="complete",
        detail=f"Generated {len(figures)} diagrams",
        message="Figure generation complete",
    )
    
    return {
        "figures": figures,
        "phase": "figures_generated"
    }
