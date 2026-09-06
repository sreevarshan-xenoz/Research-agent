"""P34: Multi-Agent Research Swarm — Data Models.

Defines the roles, structured contributions, debate turns, rounds,
consensus scoring, and persistent session state for multi-agent swarm deliberation.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SwarmRole(str, Enum):
    """Specialized roles within the research swarm."""

    THEORIST = "theorist"
    EXPERIMENTALIST = "experimentalist"
    CRITIC = "critic"
    EDITOR = "editor"
    DOMAIN_EXPERT = "domain_expert"


@dataclass
class AgentContribution:
    """A structured proposition or argument submitted by a swarm agent."""

    agent_id: str
    role: SwarmRole
    argument: str
    key_claims: list[str] = field(default_factory=list)
    methodology: str = ""
    theoretical_foundation: str = ""
    experimental_protocol: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    critiques_of_others: list[dict[str, Any]] = field(default_factory=list)
    concessions: list[str] = field(default_factory=list)
    confidence: float = 0.8
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value if isinstance(self.role, SwarmRole) else str(self.role),
            "argument": self.argument,
            "key_claims": self.key_claims,
            "methodology": self.methodology,
            "theoretical_foundation": self.theoretical_foundation,
            "experimental_protocol": self.experimental_protocol,
            "assumptions": self.assumptions,
            "critiques_of_others": self.critiques_of_others,
            "concessions": self.concessions,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentContribution:
        role_raw = data.get("role", "theorist")
        try:
            role = SwarmRole(role_raw)
        except ValueError:
            role = SwarmRole.THEORIST

        return cls(
            agent_id=data.get("agent_id", str(uuid.uuid4())[:8]),
            role=role,
            argument=data.get("argument", ""),
            key_claims=list(data.get("key_claims", [])),
            methodology=data.get("methodology", ""),
            theoretical_foundation=data.get("theoretical_foundation", ""),
            experimental_protocol=list(data.get("experimental_protocol", [])),
            assumptions=list(data.get("assumptions", [])),
            critiques_of_others=list(data.get("critiques_of_others", [])),
            concessions=list(data.get("concessions", [])),
            confidence=float(data.get("confidence", 0.8)),
            timestamp=float(data.get("timestamp", time.time())),
        )


@dataclass
class DebateRound:
    """A single round of structured swarm deliberation."""

    round_number: int
    phase: str  # "proposition", "critique", "rebuttal", "synthesis"
    contributions: list[AgentContribution] = field(default_factory=list)
    round_summary: str = ""
    agreed_points: list[str] = field(default_factory=list)
    unresolved_conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "phase": self.phase,
            "contributions": [c.to_dict() for c in self.contributions],
            "round_summary": self.round_summary,
            "agreed_points": self.agreed_points,
            "unresolved_conflicts": self.unresolved_conflicts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DebateRound:
        return cls(
            round_number=data.get("round_number", 1),
            phase=data.get("phase", "proposition"),
            contributions=[
                AgentContribution.from_dict(c) for c in data.get("contributions", [])
            ],
            round_summary=data.get("round_summary", ""),
            agreed_points=list(data.get("agreed_points", [])),
            unresolved_conflicts=list(data.get("unresolved_conflicts", [])),
        )


@dataclass
class SwarmConsensus:
    """The synthesized outcome of the multi-agent debate."""

    topic: str
    status: str  # "consensus_reached", "majority_agreement", "dissent_recorded"
    consensus_score: float  # 0.0 to 1.0
    synthesized_hypothesis: str
    theoretical_foundation: str
    experimental_plan: list[str] = field(default_factory=list)
    agreed_claims: list[str] = field(default_factory=list)
    disputed_claims: list[dict[str, Any]] = field(default_factory=list)
    dissenting_views: list[str] = field(default_factory=list)
    recommended_next_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "status": self.status,
            "consensus_score": self.consensus_score,
            "synthesized_hypothesis": self.synthesized_hypothesis,
            "theoretical_foundation": self.theoretical_foundation,
            "experimental_plan": self.experimental_plan,
            "agreed_claims": self.agreed_claims,
            "disputed_claims": self.disputed_claims,
            "dissenting_views": self.dissenting_views,
            "recommended_next_steps": self.recommended_next_steps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SwarmConsensus:
        return cls(
            topic=data.get("topic", ""),
            status=data.get("status", "consensus_reached"),
            consensus_score=float(data.get("consensus_score", 0.0)),
            synthesized_hypothesis=data.get("synthesized_hypothesis", ""),
            theoretical_foundation=data.get("theoretical_foundation", ""),
            experimental_plan=list(data.get("experimental_plan", [])),
            agreed_claims=list(data.get("agreed_claims", [])),
            disputed_claims=list(data.get("disputed_claims", [])),
            dissenting_views=list(data.get("dissenting_views", [])),
            recommended_next_steps=list(data.get("recommended_next_steps", [])),
        )


@dataclass
class DebateSession:
    """Complete multi-round research swarm debate session."""

    session_id: str
    topic: str
    context: str = ""
    roles: list[SwarmRole] = field(default_factory=list)
    rounds: list[DebateRound] = field(default_factory=list)
    consensus: SwarmConsensus | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "context": self.context,
            "roles": [r.value if isinstance(r, SwarmRole) else str(r) for r in self.roles],
            "rounds": [r.to_dict() for r in self.rounds],
            "consensus": self.consensus.to_dict() if self.consensus else None,
            "created_at": self.created_at,
        }
