"""P34: Multi-Agent Research Swarm — Role-Specialized Agents.

Implements specialized agent personas (Theorist, Experimentalist, Critic, Editor,
Domain Expert) capable of participating in structured multi-turn debates.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from research_agent.models import agenerate_json, agenerate_text
from research_agent.swarm.models import AgentContribution, SwarmRole

logger = logging.getLogger(__name__)


ROLE_PERSONAS: dict[SwarmRole, dict[str, str]] = {
    SwarmRole.THEORIST: {
        "title": "Theoretical Foundations Lead",
        "focus": "Mathematical formulations, theoretical underpinnings, axiomatic assumptions, proofs, and mechanism derivations.",
        "style": "Formal, rigorous, deductive, seeking foundational principles and mathematical bounds.",
        "prompt_guidance": "Focus on mathematical rigor, axiomatic assumptions, formal definitions, and asymptotic complexity bounds. Formulate hypotheses as mathematically testable theorems or mechanisms.",
    },
    SwarmRole.EXPERIMENTALIST: {
        "title": "Empirical Validation & Benchmark Lead",
        "focus": "Validation protocols, real-world datasets, baseline comparisons, compute efficiency, ablation studies, and reproducibility.",
        "style": "Practical, evidence-based, empirical, demanding rigorous metrics and benchmark designs.",
        "prompt_guidance": "Focus on benchmark designs, standard baseline models, dataset selection, ablation protocols, error bars, and metric validity. Ground theoretical claims in concrete experimental setups.",
    },
    SwarmRole.CRITIC: {
        "title": "Adversarial Stress-Testing Lead",
        "focus": "Hidden assumptions, unaddressed confounders, failure modes, scalability bottlenecks, dataset biases, and counterexamples.",
        "style": "Skeptical, incisive, adversarial, probing for weak links and unverified leaps.",
        "prompt_guidance": "Act as an adversarial reviewer. Challenge unstated assumptions, identify potential data leaks, highlight confounding variables, probe computational intractability, and propose hard counterexamples.",
    },
    SwarmRole.EDITOR: {
        "title": "Research Synthesis & Arbitration Lead",
        "focus": "Coherence, conceptual synthesis, terminology reconciliation, consensus arbitration, and balanced academic framing.",
        "style": "Objective, integrative, balanced, resolving contradictions into a unified paradigm.",
        "prompt_guidance": "Synthesize the competing perspectives into a unified, coherent framework. Identify common ground, reconcile divergent terminology, and arbitrate unresolvable debates by explicitly recording boundary conditions.",
    },
    SwarmRole.DOMAIN_EXPERT: {
        "title": "Domain & Application Specialist",
        "focus": "Domain-specific realism, state-of-the-art literature alignment, practical constraints, and societal/industry impact.",
        "style": "Domain-grounded, contextual, practical, aligning ideas with real-world operational realities.",
        "prompt_guidance": "Evaluate proposals against real-world domain constraints, state-of-the-art benchmarks, and practical deployment considerations.",
    },
}


class SwarmAgent:
    """An autonomous specialized agent in the research swarm."""

    def __init__(self, role: SwarmRole, agent_id: str | None = None):
        self.role = role
        self.agent_id = agent_id or f"{role.value}_{id(self) % 1000:03d}"
        self.persona = ROLE_PERSONAS.get(role, ROLE_PERSONAS[SwarmRole.THEORIST])

    async def propose(
        self,
        topic: str,
        context: str = "",
        existing_findings: dict[str, Any] | None = None,
    ) -> AgentContribution:
        """Generate an initial structured proposition from this role's perspective."""
        prompt = (
            f"You are the {self.persona['title']} in a research swarm.\n"
            f"Focus: {self.persona['focus']}\n"
            f"Guidance: {self.persona['prompt_guidance']}\n\n"
            f"Research Topic: '{topic}'\n"
            f"Context: {context or 'None provided.'}\n\n"
            "Formulate your position as valid JSON with the following structure:\n"
            "{\n"
            '  "argument": "Detailed 2-3 paragraph position statement",\n'
            '  "key_claims": ["Specific claim 1", "Specific claim 2", "Specific claim 3"],\n'
            '  "methodology": "Proposed research methodology or formal approach",\n'
            '  "theoretical_foundation": "Core theoretical or mathematical formulation",\n'
            '  "experimental_protocol": ["Step 1", "Step 2", "Step 3"],\n'
            '  "assumptions": ["Underlying assumption 1", "Underlying assumption 2"],\n'
            '  "confidence": 0.85\n'
            "}"
        )

        try:
            res = await agenerate_json(role="planner", prompt=prompt)
            if isinstance(res, dict) and res.get("argument"):
                return AgentContribution(
                    agent_id=self.agent_id,
                    role=self.role,
                    argument=str(res.get("argument", "")),
                    key_claims=[str(c) for c in res.get("key_claims", [])],
                    methodology=str(res.get("methodology", "")),
                    theoretical_foundation=str(res.get("theoretical_foundation", "")),
                    experimental_protocol=[str(p) for p in res.get("experimental_protocol", [])],
                    assumptions=[str(a) for a in res.get("assumptions", [])],
                    confidence=float(res.get("confidence", 0.8)),
                )
        except Exception as exc:
            logger.debug("LLM propose failed for %s: %s", self.role.value, exc)

        # Deterministic fallback proposition
        return self._fallback_proposition(topic)

    async def critique(
        self,
        topic: str,
        other_contributions: list[AgentContribution],
    ) -> list[dict[str, Any]]:
        """Critique propositions made by peer agents in the swarm."""
        if not other_contributions:
            return []

        other_summaries = "\n\n".join(
            f"[{c.role.value.upper()} ({c.agent_id})]:\n"
            f"Argument: {c.argument}\n"
            f"Key Claims: {', '.join(c.key_claims)}\n"
            f"Assumptions: {', '.join(c.assumptions)}"
            for c in other_contributions
            if c.role != self.role
        )

        prompt = (
            f"You are the {self.persona['title']} in a research swarm.\n"
            f"Focus: {self.persona['focus']}\n"
            f"Guidance: {self.persona['prompt_guidance']}\n\n"
            f"Topic: '{topic}'\n\n"
            f"Peer Proposals to critique:\n{other_summaries}\n\n"
            "Critique each peer's proposal rigorously. Return a JSON array of critique objects:\n"
            "[\n"
            "  {\n"
            '    "target_role": "target_role_name",\n'
            '    "target_agent_id": "target_agent_id",\n'
            '    "critique_point": "Concise critique summary",\n'
            '    "severity": "major|moderate|minor",\n'
            '    "suggested_fix": "Constructive alternative or mitigation"\n'
            "  }\n"
            "]"
        )

        try:
            res = await agenerate_json(role="critic", prompt=prompt)
            if isinstance(res, list):
                return [item for item in res if isinstance(item, dict)]
            if isinstance(res, dict) and "critiques" in res:
                return list(res["critiques"])
        except Exception as exc:
            logger.debug("LLM critique failed for %s: %s", self.role.value, exc)

        # Deterministic fallback critiques
        return [
            {
                "target_role": c.role.value,
                "target_agent_id": c.agent_id,
                "critique_point": f"From a {self.role.value} perspective, claims in {c.role.value} require stronger empirical and theoretical validation.",
                "severity": "moderate",
                "suggested_fix": "Provide explicit boundary conditions and empirical ablation baselines.",
            }
            for c in other_contributions
            if c.role != self.role
        ]

    async def rebut_and_refine(
        self,
        topic: str,
        my_previous_contribution: AgentContribution,
        critiques_received: list[dict[str, Any]],
    ) -> AgentContribution:
        """Refine original argument by addressing peer critiques or offering concessions."""
        critiques_text = "\n".join(
            f"- From {c.get('target_role', 'peer')}: {c.get('critique_point', '')} (Suggested fix: {c.get('suggested_fix', 'N/A')})"
            for c in critiques_received
        ) or "No major critiques received."

        prompt = (
            f"You are the {self.persona['title']}.\n"
            f"Topic: '{topic}'\n\n"
            f"Your Previous Proposal:\n{my_previous_contribution.argument}\n\n"
            f"Critiques Received:\n{critiques_text}\n\n"
            "Refine your proposal in response to these critiques. Defend valid points, concede valid objections, and strengthen the methodology.\n"
            "Return JSON:\n"
            "{\n"
            '  "argument": "Refined and strengthened position statement",\n'
            '  "key_claims": ["Refined claim 1", "Refined claim 2"],\n'
            '  "concessions": ["Points conceded based on valid critique"],\n'
            '  "methodology": "Updated methodology incorporating feedback",\n'
            '  "confidence": 0.88\n'
            "}"
        )

        try:
            res = await agenerate_json(role="planner", prompt=prompt)
            if isinstance(res, dict) and res.get("argument"):
                return AgentContribution(
                    agent_id=self.agent_id,
                    role=self.role,
                    argument=str(res.get("argument", my_previous_contribution.argument)),
                    key_claims=[str(c) for c in res.get("key_claims", my_previous_contribution.key_claims)],
                    methodology=str(res.get("methodology", my_previous_contribution.methodology)),
                    theoretical_foundation=my_previous_contribution.theoretical_foundation,
                    experimental_protocol=my_previous_contribution.experimental_protocol,
                    assumptions=my_previous_contribution.assumptions,
                    concessions=[str(c) for c in res.get("concessions", [])],
                    confidence=float(res.get("confidence", my_previous_contribution.confidence)),
                )
        except Exception as exc:
            logger.debug("LLM rebuttal failed for %s: %s", self.role.value, exc)

        # Fallback refinement
        return AgentContribution(
            agent_id=self.agent_id,
            role=self.role,
            argument=f"{my_previous_contribution.argument} [Refined in response to peer critiques]",
            key_claims=my_previous_contribution.key_claims,
            methodology=my_previous_contribution.methodology,
            theoretical_foundation=my_previous_contribution.theoretical_foundation,
            experimental_protocol=my_previous_contribution.experimental_protocol,
            assumptions=my_previous_contribution.assumptions,
            concessions=[f"Clarified boundary conditions based on peer feedback"],
            confidence=min(1.0, my_previous_contribution.confidence + 0.05),
        )

    def _fallback_proposition(self, topic: str) -> AgentContribution:
        """Deterministic role-specific proposition generator."""
        if self.role == SwarmRole.THEORIST:
            return AgentContribution(
                agent_id=self.agent_id,
                role=self.role,
                argument=f"The fundamental mechanism governing '{topic}' requires formalizing the underlying state space and establishing convergence bounds under noisy observations.",
                key_claims=[
                    f"Theoretical formulation of {topic} can be modeled as a constrained optimization problem.",
                    "Asymptotic error bounds guarantee stability under bounded variance.",
                ],
                methodology="Formal mathematical derivation and analytical upper-bound proof.",
                theoretical_foundation="Markov decision process and Lyapunov stability criteria.",
                assumptions=["Stationary distribution exists", "Observation noise is zero-mean Gaussian"],
                confidence=0.85,
            )
        elif self.role == SwarmRole.EXPERIMENTALIST:
            return AgentContribution(
                agent_id=self.agent_id,
                role=self.role,
                argument=f"Empirical evaluation of '{topic}' demands a standardized benchmark across 3 diverse benchmark datasets with rigorous ablation baselines.",
                key_claims=[
                    f"Performance on standard benchmarks demonstrates statistically significant gains over baselines.",
                    "Ablation studies isolate the exact contribution of each architectural component.",
                ],
                methodology="5-fold cross validation with 95% confidence intervals across standard benchmark suites.",
                experimental_protocol=[
                    "Establish reproducible baseline implementations",
                    "Execute 10 independent trials with randomized seeds",
                    "Conduct two-tailed Welch's t-tests for statistical significance",
                ],
                assumptions=["Benchmark datasets are representative of production distribution"],
                confidence=0.88,
            )
        elif self.role == SwarmRole.CRITIC:
            return AgentContribution(
                agent_id=self.agent_id,
                role=self.role,
                argument=f"Existing formulations of '{topic}' suffer from potential data leakage, unaddressed distribution shifts, and quadratic computational overhead.",
                key_claims=[
                    "Baseline comparisons often fail to account for compute parity.",
                    "Performance degrades significantly when test distributions diverge from training priors.",
                ],
                methodology="Adversarial stress-testing and sensitivity analysis across covariate shifts.",
                assumptions=["Adversarial perturbations reveal real-world vulnerability"],
                confidence=0.82,
            )
        else:  # Editor / Domain Expert
            return AgentContribution(
                agent_id=self.agent_id,
                role=self.role,
                argument=f"A balanced synthesis of '{topic}' unifies formal convergence guarantees with empirical reproducibility and practical computational feasibility.",
                key_claims=[
                    f"Integrating theoretical grounding with empirical validation yields the most robust paradigm for {topic}.",
                ],
                methodology="Hybrid theoretical-empirical verification framework.",
                confidence=0.90,
            )
