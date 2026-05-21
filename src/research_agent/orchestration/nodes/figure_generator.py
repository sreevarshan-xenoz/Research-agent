from __future__ import annotations
import json

from research_agent.models import agenerate_json, agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


async def figure_generator_node(state: GraphState) -> dict:
    """Generates Diagram/Plot code based on research findings."""
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
        "You are a technical illustrator and data scientist. Analyze the following research sections and decide what visual representation best fits the core concepts.\n\n"
        f"Topic: {state['topic']}\n\n"
        "Research Context:\n"
        f"{context}\n\n"
        "Instructions:\n"
        "1. If the text describes data trends, charts, or quantitative results, choose 'matplotlib' and write Python Matplotlib code to generate the chart.\n"
        "2. If the text describes complex software architecture, UML diagrams, or state machines, choose 'plantuml' and write PlantUML code.\n"
        "3. If the text describes simple flowcharts or block diagrams, choose 'mermaid' and write Mermaid.js code.\n"
        "4. If no diagram makes sense, choose 'none'.\n"
        "5. Output exactly one JSON object with keys: 'type' (string) and 'code' (string).\n"
    )

    figure_req = await agenerate_json(
        role="orchestrator",
        prompt=prompt,
        temperature=0.2,
        max_tokens=1500
    )

    figures = []
    if figure_req and isinstance(figure_req, dict):
        fig_type = str(figure_req.get("type", "none")).lower()
        fig_code = str(figure_req.get("code", "")).strip()

        if fig_type != "none" and fig_code:
            await apublish_progress(
                agent="Figure Generator",
                status="running",
                detail=f"Translating {fig_type.title()} to TikZ/PGF",
                message="Converting visuals for LaTeX",
            )
            
            # Translation prompt to TikZ/PGFPlots
            translate_prompt = (
                f"You are a LaTeX expert. Translate the following {fig_type.title()} source code "
                "into a high-quality LaTeX tikzpicture or pgfplots environment.\n\n"
                f"Source Code:\n{fig_code}\n\n"
                "Instructions:\n"
                "1. Output ONLY the \\begin{tikzpicture} ... \\end{tikzpicture} block.\n"
                "2. Do not use markdown code blocks.\n"
                "3. If it's a data plot, use pgfplots (e.g. \\begin{axis}). If it's a diagram, use standard TikZ nodes/edges.\n"
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
                    "caption": f"Visual representation for {state['topic']}",
                    "source_type": fig_type,
                    "source_code": fig_code
                })
            else:
                # Fallback
                figures.append({
                    "type": fig_type,
                    "content": fig_code,
                    "caption": f"Visual representation for {state['topic']}"
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
