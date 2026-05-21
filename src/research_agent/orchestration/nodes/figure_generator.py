from __future__ import annotations


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
            clean_mermaid = mermaid_code.replace("```mermaid", "").replace("```", "").strip()
            if clean_mermaid != "NO_DIAGRAM":
                await apublish_progress(
                    agent="Figure Generator",
                    status="running",
                    detail="Translating Mermaid to TikZ",
                    message="Converting visuals for LaTeX",
                )
                
                # Translation prompt
                translate_prompt = (
                    "You are a LaTeX expert. Translate the following Mermaid.js diagram code "
                    "into a high-quality LaTeX tikzpicture environment.\n\n"
                    "Mermaid Code:\n"
                    f"{clean_mermaid}\n\n"
                    "Instructions:\n"
                    "1. Output ONLY the \\begin{tikzpicture} ... \\end{tikzpicture} block.\n"
                    "2. Do not use markdown code blocks.\n"
                    "3. Use standard TikZ styles and positioning (node, edge, ->, etc.).\n"
                    "4. Ensure the output is valid LaTeX and aesthetically pleasing.\n"
                )
                
                tikz_code = await agenerate_text(
                    role="orchestrator",
                    prompt=translate_prompt,
                    temperature=0.2,
                    max_tokens=2000
                )
                
                if tikz_code and "\\begin{tikzpicture}" in tikz_code:
                    clean_tikz = tikz_code.replace("```latex", "").replace("```", "").strip()
                    figures.append({
                        "type": "tikz",
                        "content": clean_tikz,
                        "caption": f"System architecture for {state['topic']}",
                        "mermaid_source": clean_mermaid
                    })
                else:
                    # Fallback to Mermaid if translation fails
                    figures.append({
                        "type": "mermaid",
                        "content": clean_mermaid,
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
