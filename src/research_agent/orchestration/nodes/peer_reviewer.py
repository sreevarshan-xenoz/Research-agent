from __future__ import annotations

from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


async def peer_reviewer_node(state: GraphState) -> dict:
    """Acts as an automated LaTeX peer reviewer, analyzing the composed draft."""
    await apublish_progress(
        agent="Peer Reviewer",
        status="running",
        detail="Reviewing composed LaTeX",
        message="Running automated peer review",
    )
    
    latex_main = state.get("latex_main", "")
    if not latex_main:
        return {"phase": "peer_review_skipped"}

    # Provide the LLM with the LaTeX draft to generate a review
    prompt = (
        "You are an expert academic peer reviewer. Review the following LaTeX draft of a research paper.\n\n"
        f"Topic: {state['topic']}\n\n"
        "Draft LaTeX:\n"
        f"{latex_main}\n\n"
        "Instructions:\n"
        "1. Write a structured peer review report in Markdown format.\n"
        "2. Evaluate the paper on:\n"
        "   - Clarity and Structure\n"
        "   - Quality of Evidence and Citations\n"
        "   - Academic Tone\n"
        "3. Provide constructive feedback and identify any weaknesses or areas for improvement.\n"
        "4. Output ONLY the Markdown review report.\n"
    )

    review_report = await agenerate_text(
        role="orchestrator",
        prompt=prompt,
        temperature=0.3,
        max_tokens=2000
    )

    if not review_report:
        review_report = "No peer review generated due to an error."

    await apublish_progress(
        agent="Peer Reviewer",
        status="complete",
        detail="Peer review complete",
        message="Review generated",
    )
    
    return {
        "peer_review_report": review_report,
        "phase": "peer_review_complete"
    }
