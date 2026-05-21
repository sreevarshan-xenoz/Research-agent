from __future__ import annotations

from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


async def comparison_table_node(state: GraphState) -> dict:
    """Generates a LaTeX comparison table of the top cited works."""
    await apublish_progress(
        agent="Table Generator",
        status="running",
        detail="Comparing methodologies",
        message="Generating comparison table",
    )
    
    citations = state.get("citations", [])
    if not citations:
        return {"phase": "comparison_skipped"}

    # Take top 5 citations
    top_cites = citations[:5]
    source_summary = "\n".join([
        f"- {c['key']}: {c['title']} ({c['year']})"
        for c in top_cites
    ])

    prompt = (
        "You are a LaTeX and technical writing expert. Create a LaTeX comparison table for the following cited works.\n\n"
        f"Topic: {state['topic']}\n\n"
        "Cited Works:\n"
        f"{source_summary}\n\n"
        "Instructions:\n"
        "1. Columns should include: Reference, Methodology, Dataset/Domain, and Key Contribution.\n"
        "2. Use the 'tabular' or 'tabularx' environment.\n"
        "3. Ensure it is valid LaTeX that can be inserted into a paper.\n"
        "4. Keep descriptions concise to fit on a page.\n"
        "5. Output ONLY the LaTeX code block (from \\begin{table} to \\end{table}).\n"
    )

    table_code = await agenerate_text(
        role="orchestrator",
        prompt=prompt,
        temperature=0.2,
        max_tokens=1500
    )

    await apublish_progress(
        agent="Table Generator",
        status="complete",
        detail="Comparison table ready",
        message="LaTeX table generated",
    )
    
    return {
        "comparison_table": table_code,
        "phase": "comparison_generated"
    }
