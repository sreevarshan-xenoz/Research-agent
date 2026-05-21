from __future__ import annotations

import re
from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


async def formula_verifier_node(state: GraphState) -> dict:
    """Verifies LaTeX formulas for logical consistency and standard notation."""
    await apublish_progress(
        agent="Math Verifier",
        status="running",
        detail="Checking formula logic",
        message="Running mathematical consistency check",
    )
    
    latex_main = state.get("latex_main", "")
    if not latex_main:
        return {"phase": "math_skipped"}

    # Extract formulas between $ $ or \[ \] or \begin{equation}
    formulas = re.findall(r"\$.*?\$|\\\[.*?\\\]|\\begin\{equation\}.*?\\end\{equation\}", latex_main, re.DOTALL)
    if not formulas:
        return {"phase": "math_skipped"}

    formula_sample = "\n".join(formulas[:10]) # Check top 10

    prompt = (
        "You are a mathematical consultant. Verify the following LaTeX formulas for logical consistency and potential errors.\n\n"
        "Formulas:\n"
        f"{formula_sample}\n\n"
        "Instructions:\n"
        "1. Check if dimensions/units match (if applicable).\n"
        "2. Identify any standard notation errors.\n"
        "3. Look for common 'copy-paste' errors in equations.\n"
        "4. Output a Markdown 'Mathematical Verification Report'.\n"
    )

    math_report = await agenerate_text(
        role="orchestrator",
        prompt=prompt,
        temperature=0.0,
        max_tokens=1000
    )

    run_warnings = state.get("run_warnings", [])
    if math_report and "error" in math_report.lower() or "inconsistency" in math_report.lower():
         run_warnings.append("Math Verifier: Potential inconsistencies detected in formulas.")

    await apublish_progress(
        agent="Math Verifier",
        status="complete",
        detail="Formulas verified",
        message="Check complete",
    )
    
    return {
        "math_verification_report": math_report,
        "run_warnings": run_warnings,
        "phase": "math_verified"
    }
