from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from research_agent.models import agenerate_json

logger = logging.getLogger(__name__)


@dataclass
class EmpiricalClaim:
    """A single empirical claim extracted from a paper section."""
    claim_id: str
    claim_text: str
    section_title: str
    metric: str | None = None
    dataset: str | None = None
    baseline: str | None = None
    claimed_value: str | None = None
    verification_potential: float = 0.0  # 0.0–1.0 how verifiable this claim is
    context: str = ""


class ClaimExtractor:
    """Extracts empirical claims from paper sections using LLM analysis.

    Identifies claims with quantitative results, comparisons, or
    verifiable statements. Returns structured claim objects with
    metadata for code verification.
    """

    def __init__(self, min_verification_potential: float = 0.3):
        self.min_verification_potential = min_verification_potential

    async def extract_claims(
        self,
        sections: list[dict[str, Any]],
        topic: str,
    ) -> list[EmpiricalClaim]:
        """Extract empirical claims from paper sections.

        Analyzes each section for claims that can be verified through
        code execution (numerical results, comparisons, metrics, etc.).
        """
        all_claims: list[EmpiricalClaim] = []
        for section in sections:
            section_title = section.get("title", "Untitled")
            section_content = section.get("content", "")

            if not section_content.strip():
                continue

            claims = await self._extract_from_section(section_title, section_content, topic)
            all_claims.extend(claims)

        logger.info(
            "ClaimExtractor: extracted %d claims (%.1f above threshold %.2f)",
            len(all_claims),
            sum(1 for c in all_claims if c.verification_potential >= self.min_verification_potential),
            self.min_verification_potential,
        )
        return all_claims

    async def _extract_from_section(
        self,
        section_title: str,
        section_content: str,
        topic: str,
    ) -> list[EmpiricalClaim]:
        """Extract claims from a single section using LLM."""
        prompt = (
            "You are analyzing a research paper section to extract empirical claims "
            "that can be verified through code execution. Focus on claims that:\n"
            "- Report numerical results (accuracies, scores, percentages, etc.)\n"
            "- Compare methods or baselines\n"
            "- Present statistics or quantitative findings\n"
            "- Claim performance improvements or trade-offs\n\n"
            f"Research Topic: {topic}\n"
            f"Section Title: {section_title}\n\n"
            f"Section Content:\n{section_content[:8000]}\n\n"
            "For each claim found, return a JSON object with key 'claims' containing a list of objects with:\n"
            "- claim_text: the exact text of the claim\n"
            "- metric: the metric being reported (e.g., accuracy, F1, time, memory) or null\n"
            "- dataset: the dataset used (if mentioned) or null\n"
            "- baseline: the method being compared against (if applicable) or null\n"
            "- claimed_value: the specific value claimed (e.g., '95.2%', '3.4x speedup')\n"
            "- verification_potential: float 0.0-1.0 (how easily this can be verified by running code — high for numerical results, low for qualitative claims)\n"
            "- context: brief context needed to verify this claim (e.g., 'classification on ImageNet')\n\n"
            "Return an empty list if no verifiable claims are found in this section."
        )

        try:
            result = await agenerate_json(
                role="head",
                prompt=prompt,
                temperature=0.1,
            )
            if not isinstance(result, dict):
                return []

            raw_claims = result.get("claims", [])
            if not isinstance(raw_claims, list):
                return []

            claims = []
            for i, raw in enumerate(raw_claims):
                if not isinstance(raw, dict):
                    continue
                claim = EmpiricalClaim(
                    claim_id=f"claim_{section_title[:20].strip().replace(' ', '_')}_{i}",
                    claim_text=raw.get("claim_text", ""),
                    section_title=section_title,
                    metric=raw.get("metric"),
                    dataset=raw.get("dataset"),
                    baseline=raw.get("baseline"),
                    claimed_value=raw.get("claimed_value"),
                    verification_potential=float(raw.get("verification_potential", 0.0)),
                    context=raw.get("context", ""),
                )
                if claim.claim_text and claim.verification_potential >= self.min_verification_potential:
                    claims.append(claim)

            return claims
        except Exception as exc:
            logger.warning("Claim extraction failed for section '%s': %s", section_title, exc)
            return []
