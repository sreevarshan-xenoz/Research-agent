from __future__ import annotations

import logging
from dataclasses import dataclass, field
from research_agent.models import agenerate_json
from research_agent.orchestration.code_sandbox.claim_extractor import EmpiricalClaim

logger = logging.getLogger(__name__)


@dataclass
class VerificationCode:
    """Generated verification code for a single claim."""
    claim_id: str
    code: str
    language: str = "python"
    dependencies: list[str] = field(default_factory=list)
    setup_instructions: str = ""
    estimated_runtime_seconds: int = 30


class CodeGenerator:
    """Generates verification code for empirical claims using LLM.

    Takes extracted claims and paper context, produces runnable code
    that attempts to reproduce or verify each claim.
    """

    def __init__(self, max_code_length: int = 10_000):
        self.max_code_length = max_code_length

    async def generate_code(
        self,
        claim: EmpiricalClaim,
        paper_context: str = "",
    ) -> VerificationCode | None:
        """Generate verification code for a single claim."""
        prompt = (
            "You are an expert at reproducing research results from code. "
            "Given a claim from a research paper, write Python code that "
            "would verify or reproduce this claim.\n\n"
            f"Claim: {claim.claim_text}\n"
            f"Metric: {claim.metric or 'N/A'}\n"
            f"Dataset: {claim.dataset or 'N/A'}\n"
            f"Baseline: {claim.baseline or 'N/A'}\n"
            f"Claimed Value: {claim.claimed_value or 'N/A'}\n"
            f"Context: {claim.context}\n\n"
            f"Section Source: {claim.section_title}\n"
        )

        if paper_context:
            prompt += f"\nPaper context:\n{paper_context[:4000]}\n"

        prompt += (
            "\nWrite Python code that:\n"
            "1. Uses standard libraries (numpy, scipy, sklearn, etc.) — import what you need\n"
            "2. Either reproduces the claimed result or runs an equivalent verification\n"
            "3. Prints the key output clearly so it can be compared to the claimed value\n"
            "4. Handles errors gracefully\n"
            "5. Runs within 60 seconds\n\n"
            "Return a JSON object with keys:\n"
            "- code: the full Python code as a string\n"
            "- dependencies: list of pip packages needed (e.g., ['numpy', 'scipy'])\n"
            "- setup_instructions: any setup notes (or empty string)\n"
            "- estimated_runtime_seconds: int, estimated runtime in seconds\n\n"
            "IMPORTANT: Return ONLY valid JSON. Do not include markdown formatting or code fences."
        )

        try:
            result = await agenerate_json(
                role="head",
                prompt=prompt,
                temperature=0.2,
            )
            if not isinstance(result, dict) or "code" not in result:
                logger.warning("Code generation returned no code for claim %s", claim.claim_id)
                return None

            code = result.get("code", "")
            if not code.strip():
                return None

            # Truncate if too long
            if len(code) > self.max_code_length:
                code = code[:self.max_code_length]
                logger.warning("Code for claim %s truncated to %d chars", claim.claim_id, self.max_code_length)

            return VerificationCode(
                claim_id=claim.claim_id,
                code=code,
                language=result.get("language", "python"),
                dependencies=result.get("dependencies", []),
                setup_instructions=result.get("setup_instructions", ""),
                estimated_runtime_seconds=result.get("estimated_runtime_seconds", 30),
            )
        except Exception as exc:
            logger.error("Code generation failed for claim %s: %s", claim.claim_id, exc)
            return None

    async def generate_codes(
        self,
        claims: list[EmpiricalClaim],
        paper_context: str = "",
    ) -> list[VerificationCode]:
        """Generate verification code for multiple claims."""
        results: list[VerificationCode] = []
        for claim in claims:
            code = await self.generate_code(claim, paper_context)
            if code is not None:
                results.append(code)
        logger.info(
            "CodeGenerator: generated code for %d/%d claims",
            len(results), len(claims),
        )
        return results
