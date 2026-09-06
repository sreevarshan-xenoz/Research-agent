"""P34: Multi-Agent Research Swarm — API Routes.

Exposes REST endpoints for initiating on-demand multi-agent debates,
inspecting role personas, and synthesizing multi-perspective consensus.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from research_agent.config import load_settings
from research_agent.swarm.agents import ROLE_PERSONAS
from research_agent.swarm.consensus import synthesize_swarm_consensus
from research_agent.swarm.coordinator import SwarmCoordinator
from research_agent.swarm.models import AgentContribution, SwarmRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/swarm", tags=["Swarm"])


class DebateRequest(BaseModel):
    """Request payload to initiate a multi-agent swarm debate."""
    topic: str = Field(..., description="Research topic or proposition to debate")
    context: str = Field(default="", description="Additional background findings or context")
    roles: list[str] | None = Field(default=None, description="Specific roles to participate (default: all)")
    max_rounds: int = Field(default=3, ge=1, le=5, description="Max debate rounds")
    consensus_threshold: float = Field(default=0.70, ge=0.1, le=1.0, description="Agreement threshold")


class SynthesizeRequest(BaseModel):
    """Request payload to synthesize multiple viewpoints into consensus."""
    topic: str = Field(..., description="The core research topic")
    arguments: list[dict[str, Any]] = Field(..., description="List of agent arguments with role and argument text")
    threshold: float = Field(default=0.70, ge=0.1, le=1.0)


@router.get("/roles")
async def get_swarm_roles() -> dict[str, Any]:
    """List available role personas within the research swarm."""
    roles_data = []
    for role_enum, persona in ROLE_PERSONAS.items():
        roles_data.append({
            "role": role_enum.value,
            "title": persona["title"],
            "focus": persona["focus"],
            "style": persona["style"],
            "guidance": persona["prompt_guidance"],
        })
    return {
        "status": "success",
        "count": len(roles_data),
        "roles": roles_data,
    }


@router.post("/debate")
async def run_swarm_debate_endpoint(req: DebateRequest) -> dict[str, Any]:
    """Execute an on-demand multi-agent debate session."""
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="Topic must not be empty")

    settings = load_settings()
    active_roles = req.roles or settings.swarm.roles

    try:
        coordinator = SwarmCoordinator(
            roles=active_roles,
            max_rounds=req.max_rounds,
            consensus_threshold=req.consensus_threshold,
        )

        session = await coordinator.run_debate(
            topic=req.topic.strip(),
            context=req.context.strip(),
        )

        return {
            "status": "success",
            "session": session.to_dict(),
        }
    except Exception as exc:
        logger.exception("Swarm debate failed")
        raise HTTPException(status_code=500, detail=f"Swarm debate failed: {exc}") from exc


@router.post("/synthesize")
async def synthesize_arguments_endpoint(req: SynthesizeRequest) -> dict[str, Any]:
    """Synthesize arbitrary arguments into a unified consensus."""
    if not req.arguments:
        raise HTTPException(status_code=400, detail="Arguments list cannot be empty")

    contributions = []
    for i, arg in enumerate(req.arguments):
        role_str = arg.get("role", "theorist")
        try:
            role = SwarmRole(role_str)
        except ValueError:
            role = SwarmRole.THEORIST

        contributions.append(AgentContribution(
            agent_id=f"agent_{i}",
            role=role,
            argument=str(arg.get("argument", "")),
            key_claims=list(arg.get("key_claims", [])),
            theoretical_foundation=str(arg.get("theoretical_foundation", "")),
            experimental_protocol=list(arg.get("experimental_protocol", [])),
            confidence=float(arg.get("confidence", 0.8)),
        ))

    try:
        consensus = await synthesize_swarm_consensus(
            topic=req.topic,
            contributions=contributions,
            critiques=[],
            threshold=req.threshold,
        )

        return {
            "status": "success",
            "consensus": consensus.to_dict(),
        }
    except Exception as exc:
        logger.exception("Synthesis failed")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {exc}") from exc


@router.get("/health")
async def get_swarm_health() -> dict[str, Any]:
    """Check swarm system health and configuration."""
    settings = load_settings()
    return {
        "status": "healthy",
        "enabled": settings.swarm.enabled,
        "default_roles": settings.swarm.roles,
        "max_rounds": settings.swarm.max_rounds,
        "consensus_threshold": settings.swarm.consensus_threshold,
        "available_personas": [r.value for r in SwarmRole],
    }
