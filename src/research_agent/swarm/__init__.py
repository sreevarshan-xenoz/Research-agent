"""P34: Multi-Agent Research Swarm package."""

from research_agent.swarm.models import (
    AgentContribution,
    DebateRound,
    DebateSession,
    SwarmConsensus,
    SwarmRole,
)
from research_agent.swarm.agents import SwarmAgent, ROLE_PERSONAS
from research_agent.swarm.consensus import (
    calculate_consensus_score,
    extract_agreed_and_disputed_claims,
    synthesize_swarm_consensus,
)
from research_agent.swarm.coordinator import SwarmCoordinator

__all__ = [
    "AgentContribution",
    "DebateRound",
    "DebateSession",
    "SwarmConsensus",
    "SwarmRole",
    "SwarmAgent",
    "ROLE_PERSONAS",
    "calculate_consensus_score",
    "extract_agreed_and_disputed_claims",
    "synthesize_swarm_consensus",
    "SwarmCoordinator",
]
