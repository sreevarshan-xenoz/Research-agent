from __future__ import annotations

import logging
from pathlib import Path

from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.output.grant_proposal import generate_grant_proposal

logger = logging.getLogger(__name__)


async def grant_proposal_node(state: GraphState) -> dict:
    """Orchestrates LLM-based grant proposal draft generation based on paper outcomes,
    peer review feedback, and target templates. Writes it to grant_proposal.md in the artifacts folder.
    """
    await apublish_progress(
        agent="Grant Proposal Gen",
        status="running",
        detail="Composing project summary",
        message="Drafting grant proposal",
    )

    topic = state.get("topic", "")
    run_id = state["run_id"]
    artifact_root = state.get("artifact_root", ".runtime/artifacts")
    run_dir = Path(artifact_root) / run_id

    peer_review = state.get("peer_review_report", "") or "No peer review available."
    math_verification = state.get("math_verification_report", "") or ""

    prompt = (
        f"You are an expert academic grant writer. Draft a detailed National Science Foundation (NSF) Grant Proposal "
        f"for a project based on the following research topic and outputs.\n\n"
        f"Project Title/Topic: {topic}\n\n"
        f"Peer Review Feedback:\n{peer_review}\n\n"
        f"Math/Code Verification Report:\n{math_verification}\n\n"
        f"The grant proposal MUST contain the following sections:\n"
        f"1. Project Summary (comprising Overview, Intellectual Merit, and Broader Impacts)\n"
        f"2. Project Description (including Problem Statement, Methodology, Timeline, and Expected Impact)\n"
        f"3. References Cited\n"
        f"4. Budget Justification (requesting $500,000 for personnel, computing hardware, and travel)\n"
        f"5. Data Management Plan\n\n"
        f"Write the entire proposal in professional academic Markdown."
    )

    try:
        proposal_content = await agenerate_text(
            role="orchestrator",
            prompt=prompt,
            temperature=0.2
        )
    except Exception as e:
        logger.error(f"LLM grant proposal generation failed: {e}. Falling back to deterministic draft.")
        proposal_content = generate_grant_proposal(
            title=topic or "Research Project",
            pi_name="Dr. Alex Researcher",
            pi_institution="Stanford University",
            abstract="Project abstract based on findings.",
            papers=[],
            agency="nsf"
        )

    run_dir.mkdir(parents=True, exist_ok=True)
    proposal_file = run_dir / "grant_proposal.md"
    try:
        proposal_file.write_text(proposal_content or "", encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to write grant_proposal.md: {e}")

    await apublish_progress(
        agent="Grant Proposal Gen",
        status="complete",
        detail="Generated NSF grant proposal draft",
        message="Proposal generation complete",
    )

    return {}
