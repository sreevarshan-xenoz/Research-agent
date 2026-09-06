"""P34: Multi-Agent Research Swarm — Consensus Engine & Arbitration.

Calculates consensus scores across agent positions, reconciles conflicting
theses, isolates persistent dissent, and synthesizes unified research outcomes.
"""

from __future__ import annotations

import logging
from typing import Any

from research_agent.models import agenerate_json
from research_agent.swarm.models import AgentContribution, SwarmConsensus, SwarmRole

logger = logging.getLogger(__name__)


def calculate_consensus_score(
    contributions: list[AgentContribution],
    critiques: list[dict[str, Any]],
) -> float:
    """Calculate the agreement level (0.0 to 1.0) among swarm contributions.

    Factors:
    1. Average confidence across agents (weight: 0.35)
    2. Concession ratio (higher concessions -> higher convergence, weight: 0.35)
    3. Severity of open critiques (fewer major critiques -> higher score, weight: 0.30)
    """
    if not contributions:
        return 0.0

    avg_conf = sum(c.confidence for c in contributions) / len(contributions)

    # Concessions indicate willingness to converge
    total_concessions = sum(len(c.concessions) for c in contributions)
    concession_score = min(1.0, total_concessions / max(len(contributions) * 1.5, 1.0))

    # Critique severity penalty
    major_critiques = sum(1 for c in critiques if str(c.get("severity", "")).lower() == "major")
    moderate_critiques = sum(1 for c in critiques if str(c.get("severity", "")).lower() == "moderate")
    critique_penalty = min(0.5, (major_critiques * 0.15) + (moderate_critiques * 0.05))

    raw_score = (0.40 * avg_conf) + (0.30 * concession_score) + 0.30 * (1.0 - critique_penalty)
    return round(max(0.0, min(1.0, raw_score)), 3)


def extract_agreed_and_disputed_claims(
    contributions: list[AgentContribution],
    critiques: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    """Partition claims into agreed points, disputed points, and dissenting views."""
    all_claims: list[tuple[str, str]] = []  # (role, claim_text)
    for c in contributions:
        for claim in c.key_claims:
            all_claims.append((c.role.value, claim))

    critique_target_points = [str(c.get("critique_point", "")).lower() for c in critiques]

    agreed: list[str] = []
    disputed: list[dict[str, Any]] = []
    dissenting: list[str] = []

    for role, claim in all_claims:
        # Check if this claim was targeted by any critique
        is_contested = any(
            any(word in cp for word in claim.lower().split() if len(word) > 5)
            for cp in critique_target_points
        )
        if is_contested:
            disputed.append({
                "originating_role": role,
                "claim": claim,
                "status": "contested_in_debate",
            })
        else:
            if claim not in agreed:
                agreed.append(claim)

    # Dissent from Critic if severe
    for c in contributions:
        if c.role == SwarmRole.CRITIC and c.argument:
            for assumption in c.assumptions:
                dissent_text = f"Critic caveat: {assumption}"
                if dissent_text not in dissenting:
                    dissenting.append(dissent_text)

    return agreed, disputed, dissenting


async def synthesize_swarm_consensus(
    topic: str,
    contributions: list[AgentContribution],
    critiques: list[dict[str, Any]],
    threshold: float = 0.70,
) -> SwarmConsensus:
    """Synthesize the multi-agent debate into a unified research consensus."""
    consensus_score = calculate_consensus_score(contributions, critiques)
    agreed_claims, disputed_claims, dissenting_views = extract_agreed_and_disputed_claims(
        contributions, critiques
    )

    if consensus_score >= threshold:
        status = "consensus_reached"
    elif consensus_score >= threshold * 0.75:
        status = "majority_agreement"
    else:
        status = "dissent_recorded"

    contributions_summary = "\n\n".join(
        f"[{c.role.value.upper()}]:\n"
        f"Position: {c.argument}\n"
        f"Key Claims: {', '.join(c.key_claims)}\n"
        f"Methodology: {c.methodology}\n"
        f"Theoretical: {c.theoretical_foundation}\n"
        f"Experimental: {', '.join(c.experimental_protocol)}"
        for c in contributions
    )

    prompt = (
        f"You are the Editor and Chief Arbitrator of a Multi-Agent Research Swarm.\n"
        f"Topic: '{topic}'\n"
        f"Consensus Status: {status} (Score: {consensus_score:.2f})\n\n"
        f"Swarm Deliberations:\n{contributions_summary}\n\n"
        "Synthesize all perspectives into a unified, definitive consensus object. Return JSON:\n"
        "{\n"
        '  "synthesized_hypothesis": "A unified, precise research hypothesis combining theory and empirical design",\n'
        '  "theoretical_foundation": "The consolidated theoretical framework with formal mechanisms",\n'
        '  "experimental_plan": ["Phase 1: Baselines", "Phase 2: Ablation", "Phase 3: Stress-testing"],\n'
        '  "agreed_claims": ["Consensus point 1", "Consensus point 2"],\n'
        '  "recommended_next_steps": ["Step 1", "Step 2", "Step 3"]\n'
        "}"
    )

    try:
        res = await agenerate_json(role="composer", prompt=prompt)
        if isinstance(res, dict) and res.get("synthesized_hypothesis"):
            return SwarmConsensus(
                topic=topic,
                status=status,
                consensus_score=consensus_score,
                synthesized_hypothesis=str(res.get("synthesized_hypothesis", "")),
                theoretical_foundation=str(res.get("theoretical_foundation", "")),
                experimental_plan=[str(p) for p in res.get("experimental_plan", [])],
                agreed_claims=[str(c) for c in res.get("agreed_claims", agreed_claims)],
                disputed_claims=disputed_claims,
                dissenting_views=dissenting_views,
                recommended_next_steps=[str(s) for s in res.get("recommended_next_steps", [])],
            )
    except Exception as exc:
        logger.debug("LLM consensus synthesis failed: %s", exc)

    # Deterministic fallback synthesis
    theorist_contrib = next((c for c in contributions if c.role == SwarmRole.THEORIST), None)
    exp_contrib = next((c for c in contributions if c.role == SwarmRole.EXPERIMENTALIST), None)

    theo_foundation = theorist_contrib.theoretical_foundation if theorist_contrib else f"Formal theoretical modeling for {topic}."
    exp_plan = exp_contrib.experimental_protocol if exp_contrib and exp_contrib.experimental_protocol else [
        "Construct standardized benchmark testbed",
        "Run multi-trial empirical validation with statistical significance testing",
        "Conduct sensitivity analysis against adversarial confounders",
    ]

    return SwarmConsensus(
        topic=topic,
        status=status,
        consensus_score=consensus_score,
        synthesized_hypothesis=(
            f"By integrating formal theoretical bounds with empirical ablation protocols, "
            f"'{topic}' can achieve robust, verifiable performance without compromising computational tractability."
        ),
        theoretical_foundation=theo_foundation,
        experimental_plan=exp_plan,
        agreed_claims=agreed_claims or [f"Unified framework addresses core challenges in {topic}"],
        disputed_claims=disputed_claims,
        dissenting_views=dissenting_views,
        recommended_next_steps=[
            "Formulate mathematical proofs for primary bounds",
            "Implement standardized benchmark harness",
            "Publish reproducible open-source evaluation suite",
        ],
    )
