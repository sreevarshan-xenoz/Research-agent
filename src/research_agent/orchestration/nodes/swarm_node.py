"""P34: Multi-Agent Research Swarm — Graph Node.

Executes multi-agent swarm deliberation across Theorist, Experimentalist,
Critic, and Editor personas to debate and synthesize novel research perspectives.
"""

from __future__ import annotations

import logging
from typing import Any

from research_agent.config import load_settings
from research_agent.observability import apublish_progress
from research_agent.observability.logging import ErrorSeverity, log_error
from research_agent.orchestration.state import GraphState
from research_agent.swarm.coordinator import SwarmCoordinator

logger = logging.getLogger(__name__)


async def swarm_node(state: GraphState) -> dict[str, Any]:
    """Execute multi-agent research swarm deliberation."""
    settings = load_settings()
    if not settings.swarm.enabled:
        return {
            "swarm_session": state.get("swarm_session"),
            "swarm_consensus": state.get("swarm_consensus"),
        }

    topic = str(state.get("topic", ""))
    task_findings = state.get("task_findings", {})
    generated_hypotheses = state.get("generated_hypotheses", [])

    # Build context from findings and hypotheses
    context_parts = []
    if generated_hypotheses:
        context_parts.append("Initial Hypotheses:\n" + "\n".join(
            f"- {h.get('hypothesis', '')} (Rationale: {h.get('rationale', '')})"
            for h in generated_hypotheses if isinstance(h, dict)
        ))

    context_str = "\n\n".join(context_parts)

    await apublish_progress(
        agent="SwarmCoordinator",
        status="running",
        detail=f"Initiating {len(settings.swarm.roles)}-agent swarm debate across {settings.swarm.max_rounds} rounds",
        message="Starting multi-agent research swarm",
    )

    try:
        coordinator = SwarmCoordinator(
            roles=settings.swarm.roles,
            max_rounds=settings.swarm.max_rounds,
            consensus_threshold=settings.swarm.consensus_threshold,
        )

        session = await coordinator.run_debate(
            topic=topic,
            context=context_str,
            existing_findings=task_findings,
        )

        consensus_dict = session.consensus.to_dict() if session.consensus else None
        session_dict = session.to_dict()

        await apublish_progress(
            agent="SwarmCoordinator",
            status="complete",
            detail=f"Swarm debate reached '{session.consensus.status if session.consensus else 'finished'}' (Score: {session.consensus.consensus_score if session.consensus else 0.0:.2f})",
            message="Multi-agent debate concluded",
        )

        return {
            "swarm_session": session_dict,
            "swarm_consensus": consensus_dict,
        }
    except Exception as exc:
        log_error(
            "Swarm node execution failed",
            severity=ErrorSeverity.RECOVERABLE,
            component="swarm_node",
            detail=str(exc),
        )
        return {
            "swarm_session": None,
            "swarm_consensus": None,
        }
