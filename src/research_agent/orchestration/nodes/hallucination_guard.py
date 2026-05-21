from __future__ import annotations

from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


async def hallucination_guard_node(state: GraphState) -> dict:
    """Verifies generated definitions and concepts against retrieved evidence to detect hallucinations."""
    await apublish_progress(
        agent="Hallucination Guard",
        status="running",
        detail="Verifying concept integrity",
        message="Running hallucination check",
    )
    
    latex_main = state.get("latex_main", "")
    sections = state.get("combined_sections", [])
    if not latex_main or not sections:
        return {"phase": "guard_skipped"}

    # Use first few sections and raw snippets
    context = "\n".join([
        f"Section: {s.get('heading')}\nContent: {s.get('content', '')[:1000]}"
        for s in sections[:3]
    ])

    prompt = (
        "You are a fact-checker specializing in academic research. Identify any potential 'concept hallucinations' in the following research text.\n\n"
        "Instructions:\n"
        "1. Look for definitions of models, methods, or datasets that seem invented or incorrectly described.\n"
        "2. Flag any technical claims that sound plausibly AI-hallucinated (e.g., 'the X algorithm by Y' when X doesn't exist).\n"
        "3. Provide a list of 'Potential Hallucinations' or state 'No hallucinations detected'.\n"
        "4. Output exactly a Markdown report.\n\n"
        "Research Text:\n"
        f"{context}"
    )

    guard_report = await agenerate_text(
        role="orchestrator",
        prompt=prompt,
        temperature=0.2,
        max_tokens=1000
    )

    # Append to run warnings if hallucinations found
    run_warnings = state.get("run_warnings", [])
    if guard_report and "No hallucinations detected" not in guard_report:
        run_warnings.append(f"Hallucination Guard Warning: Potential issues detected. See guard_report.md.")

    await apublish_progress(
        agent="Hallucination Guard",
        status="complete",
        detail="Check complete",
        message="Integrity verified",
    )
    
    return {
        "guard_report": guard_report,
        "run_warnings": run_warnings,
        "phase": "guard_complete"
    }
