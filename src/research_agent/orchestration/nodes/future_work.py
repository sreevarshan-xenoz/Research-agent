from __future__ import annotations

from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


async def future_work_extrapolator_node(state: GraphState) -> dict:
    """Synthesizes high-impact future research directions from cited literature."""
    await apublish_progress(
        agent="Future Extrapolator",
        status="running",
        detail="Analyzing research gaps",
        message="Synthesizing future research agenda",
    )
    
    sections = state.get("combined_sections", [])
    if not sections:
        return {"phase": "future_work_skipped"}

    # Provide context to LLM
    context = "\n".join([
        f"Section: {s.get('heading')}\nContent: {s.get('content', '')[:800]}"
        for s in sections[:5]
    ])

    prompt = (
        "You are a visionary researcher and grant writer. Analyze the following research synthesis and extrapolate a future research agenda.\n\n"
        f"Topic: {state['topic']}\n\n"
        "Research Synthesis:\n"
        f"{context}\n\n"
        "Instructions:\n"
        "1. Identify at least 3 high-impact open problems or research gaps.\n"
        "2. For each gap, propose a novel technical approach or methodology.\n"
        "3. Discuss the potential impact of solving these problems.\n"
        "4. Output a structured 'Future Research Agenda' in Markdown.\n"
    )

    agenda = await agenerate_text(
        role="orchestrator",
        prompt=prompt,
        temperature=0.4,
        max_tokens=1500
    )

    await apublish_progress(
        agent="Future Extrapolator",
        status="complete",
        detail="Future agenda synthesized",
        message="Analysis complete",
    )
    
    return {
        "future_research_agenda": agenda,
        "phase": "future_work_complete"
    }
