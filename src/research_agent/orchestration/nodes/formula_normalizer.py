from __future__ import annotations

from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


async def formula_normalizer_node(state: GraphState) -> dict:
    """Post-processes the LaTeX body to ensure consistent mathematical notation styling."""
    await apublish_progress(
        agent="Formula Normalizer",
        status="running",
        detail="Standardizing math notation",
        message="Normalizing LaTeX formulas",
    )
    
    latex_main = state.get("latex_main", "")
    if not latex_main:
        return {"phase": "formula_norm_skipped"}

    prompt = (
        "You are a LaTeX copy-editor. Standardize the mathematical notation in the following LaTeX draft.\n\n"
        "Instructions:\n"
        "1. Ensure all vectors use bold notation (e.g., \\mathbf{v}).\n"
        "2. Ensure all matrices use uppercase bold (e.g., \\mathbf{A}).\n"
        "3. Use standard AMS-LaTeX conventions where applicable.\n"
        "4. DO NOT change the text content or citations.\n"
        "5. Output the FULL corrected LaTeX body.\n\n"
        "Draft LaTeX:\n"
        f"{latex_main}"
    )

    normalized_latex = await agenerate_text(
        role="orchestrator",
        prompt=prompt,
        temperature=0.1,
        max_tokens=4000
    )

    if not normalized_latex or len(normalized_latex) < 100:
         # Safety: if LLM returns garbage or too short, keep original
         normalized_latex = latex_main

    await apublish_progress(
        agent="Formula Normalizer",
        status="complete",
        detail="Notation standardized",
        message="Formula normalization complete",
    )
    
    return {
        "latex_main": normalized_latex,
        "phase": "formula_norm_complete"
    }
