"""P34: Multi-Agent Research Swarm — Swarm Coordinator.

Orchestrates multi-agent research swarms, managing role instantiation,
multi-turn debate rounds, cross-examination, and final consensus synthesis.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from research_agent.swarm.agents import SwarmAgent
from research_agent.swarm.consensus import synthesize_swarm_consensus
from research_agent.swarm.models import (
    AgentContribution,
    DebateRound,
    DebateSession,
    SwarmConsensus,
    SwarmRole,
)

logger = logging.getLogger(__name__)


class SwarmCoordinator:
    """Coordinates multi-agent debate and research synthesis."""

    def __init__(
        self,
        roles: list[str | SwarmRole] | None = None,
        max_rounds: int = 3,
        consensus_threshold: float = 0.70,
    ):
        self.max_rounds = max(1, min(max_rounds, 5))
        self.consensus_threshold = consensus_threshold

        role_enums: list[SwarmRole] = []
        if roles:
            for r in roles:
                if isinstance(r, SwarmRole):
                    role_enums.append(r)
                else:
                    try:
                        role_enums.append(SwarmRole(r.lower()))
                    except ValueError:
                        role_enums.append(SwarmRole.THEORIST)
        else:
            role_enums = [
                SwarmRole.THEORIST,
                SwarmRole.EXPERIMENTALIST,
                SwarmRole.CRITIC,
                SwarmRole.EDITOR,
            ]

        self.roles = role_enums
        self.agents = [SwarmAgent(role=r) for r in self.roles]

    async def run_debate(
        self,
        topic: str,
        context: str = "",
        existing_findings: dict[str, Any] | None = None,
    ) -> DebateSession:
        """Execute a complete multi-round research swarm debate session."""
        session_id = f"swarm_{uuid.uuid4().hex[:10]}"
        session = DebateSession(
            session_id=session_id,
            topic=topic,
            context=context,
            roles=self.roles,
        )

        logger.info(
            "Starting Swarm Debate session %s for topic: '%s' with %d agents",
            session_id, topic, len(self.agents),
        )

        # ── Round 1: Initial Propositions ─────────────────────────────────────
        logger.info("[Swarm Round 1] Generating initial propositions...")
        prop_tasks = [
            agent.propose(topic, context=context, existing_findings=existing_findings)
            for agent in self.agents
        ]
        initial_contributions = await asyncio.gather(*prop_tasks)

        round_1 = DebateRound(
            round_number=1,
            phase="proposition",
            contributions=list(initial_contributions),
            round_summary=f"Initial positions established by {len(initial_contributions)} swarm agents.",
        )
        session.rounds.append(round_1)

        current_contributions = list(initial_contributions)
        all_critiques: list[dict[str, Any]] = []

        # ── Rounds 2 to N: Critique and Rebuttal ────────────────────────────────
        for r_num in range(2, self.max_rounds + 1):
            logger.info("[Swarm Round %d] Cross-critiques and rebuttals...", r_num)

            # Generate cross-critiques
            critique_tasks = [
                agent.critique(topic, current_contributions)
                for agent in self.agents
            ]
            round_critiques_nested = await asyncio.gather(*critique_tasks)
            round_critiques = [
                item for sublist in round_critiques_nested for item in sublist
            ]
            all_critiques.extend(round_critiques)

            # Generate rebuttals and refinements
            rebuttal_tasks = []
            for agent, prev_contrib in zip(self.agents, current_contributions):
                my_critiques = [
                    c for c in round_critiques
                    if str(c.get("target_role", "")).lower() == agent.role.value
                    or str(c.get("target_agent_id", "")) == agent.agent_id
                ]
                rebuttal_tasks.append(
                    agent.rebut_and_refine(topic, prev_contrib, my_critiques)
                )

            refined_contributions = await asyncio.gather(*rebuttal_tasks)
            current_contributions = list(refined_contributions)

            r_phase = "rebuttal" if r_num < self.max_rounds else "convergence"
            round_obj = DebateRound(
                round_number=r_num,
                phase=r_phase,
                contributions=current_contributions,
                round_summary=f"Round {r_num} addressed {len(round_critiques)} peer critiques.",
            )
            session.rounds.append(round_obj)

        # ── Final Round: Consensus Synthesis ──────────────────────────────────
        logger.info("[Swarm Consensus] Synthesizing final research consensus...")
        consensus = await synthesize_swarm_consensus(
            topic=topic,
            contributions=current_contributions,
            critiques=all_critiques,
            threshold=self.consensus_threshold,
        )
        session.consensus = consensus

        logger.info(
            "Swarm debate %s finished with status '%s' (score: %.2f)",
            session_id, consensus.status, consensus.consensus_score,
        )

        return session

    def allocate_task(self, task_type: str) -> SwarmRole:
        """Dynamically allocate research tasks to the most suitable swarm role."""
        task_type_lower = task_type.lower()
        if any(w in task_type_lower for w in ["math", "formal", "theory", "proof", "bound", "axiom"]):
            return SwarmRole.THEORIST
        elif any(w in task_type_lower for w in ["benchmark", "dataset", "ablation", "metric", "eval", "experiment"]):
            return SwarmRole.EXPERIMENTALIST
        elif any(w in task_type_lower for w in ["bias", "limitation", "flaw", "stress", "attack", "critic", "risk"]):
            return SwarmRole.CRITIC
        elif any(w in task_type_lower for w in ["domain", "application", "clinical", "industry", "field"]):
            return SwarmRole.DOMAIN_EXPERT
        else:
            return SwarmRole.EDITOR
