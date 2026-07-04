from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from research_agent.orchestration.code_sandbox.claim_extractor import EmpiricalClaim
from research_agent.orchestration.code_sandbox.execution_engine import ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Comparison of an executed result against a claimed value."""
    claim_id: str
    claim_text: str
    status: str  # "pass", "fail", "partial", "unverifiable"
    claimed_value: str | None
    actual_value: str | None
    confidence: float  # 0.0–1.0 how confident we are in this comparison
    evidence: str = ""
    details: str = ""


class ResultComparator:
    """Compares execution results against claimed values.

    Uses pattern matching and LLM analysis to determine whether
    the actual output matches the claimed value.
    """

    # Common number patterns in output
    NUMBER_PATTERN = re.compile(
        r"[-+]?(?:\d+\.?\d*|\d*\.?\d+)(?:[eE][-+]?\d+)?%?"
    )

    async def compare(
        self,
        claim: EmpiricalClaim,
        execution_result: ExecutionResult,
    ) -> ComparisonResult:
        """Compare an executed result against its claimed value."""
        stdout = execution_result.sandbox_result.stdout
        stderr = execution_result.sandbox_result.stderr

        if not claim.claimed_value:
            return ComparisonResult(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                status="unverifiable",
                claimed_value=None,
                actual_value=None,
                confidence=0.0,
                evidence="No claimed value to compare against",
            )

        if not execution_result.sandbox_result.success:
            return ComparisonResult(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                status="fail",
                claimed_value=claim.claimed_value,
                actual_value=stderr[:500] if stderr else "Execution failed",
                confidence=0.8,
                evidence=f"Code exited with code {execution_result.sandbox_result.exit_code}",
                details=f"stderr: {stderr[:1000] if stderr else 'None'}",
            )

        # Try direct number comparison
        direct_result = self._compare_numbers(claim.claimed_value, stdout)
        if direct_result is not None:
            direct_result.claim_id = claim.claim_id
            direct_result.claim_text = claim.claim_text
            return direct_result

        # Fall back to LLM-based comparison for complex claims
        return await self._llm_compare(claim, execution_result)

    def _compare_numbers(
        self,
        claimed_value: str,
        actual_output: str,
    ) -> ComparisonResult | None:
        """Try to extract and compare numbers from claim and output."""
        claimed_numbers = self.NUMBER_PATTERN.findall(claimed_value)
        if not claimed_numbers:
            return None

        output_numbers = self.NUMBER_PATTERN.findall(actual_output)
        if not output_numbers:
            return None

        # Try to match the most significant claimed number
        for cn in claimed_numbers:
            cn_clean = cn.strip().rstrip("%")
            try:
                cn_val = float(cn_clean)
            except ValueError:
                continue

            for on in output_numbers:
                on_clean = on.strip().rstrip("%")
                try:
                    on_val = float(on_clean)
                except ValueError:
                    continue

                # Check if numbers match within tolerance
                if cn_val == 0:
                    matches = abs(on_val) < 0.001
                else:
                    rel_diff = abs(on_val - cn_val) / abs(cn_val)
                    matches = rel_diff < 0.05  # Within 5%

                if matches:
                    is_percentage = "%" in cn or "%" in on
                    return ComparisonResult(
                        claim_id="",
                        claim_text="",
                        status="pass",
                        claimed_value=claimed_value,
                        actual_value=f"{on_val}{'%' if is_percentage else ''}",
                        confidence=0.9,
                        evidence=f"Numerical match: claimed {cn_val}, got {on_val} (relative diff: {rel_diff:.4f})",
                    )

        # No exact match — partial match
        return ComparisonResult(
            claim_id="",
            claim_text="",
            status="partial",
            claimed_value=claimed_value,
            actual_value=f"Found values: {', '.join(output_numbers[:5])}",
            confidence=0.5,
            evidence=f"Claimed {claimed_value}, output contains numbers: {', '.join(output_numbers[:5])}",
        )

    async def _llm_compare(
        self,
        claim: EmpiricalClaim,
        execution_result: ExecutionResult,
    ) -> ComparisonResult:
        """Use LLM to compare claim against execution output."""
        from research_agent.models import agenerate_json

        prompt = (
            "Compare a claimed research result against actual code execution output "
            "and determine if the claim is verified.\n\n"
            f"Claim text: {claim.claim_text}\n"
            f"Claimed value: {claim.claimed_value or 'Not specified'}\n"
            f"Code stdout:\n{execution_result.sandbox_result.stdout[:3000]}\n"
            f"Code stderr:\n{execution_result.sandbox_result.stderr[:1000] if execution_result.sandbox_result.stderr else 'None'}\n"
            f"Exit code: {execution_result.sandbox_result.exit_code}\n\n"
            "Return a JSON object with:\n"
            "- status: one of 'pass', 'fail', 'partial', 'unverifiable'\n"
            "- actual_value: the actual measured value from the output (or null if not found)\n"
            "- confidence: float 0.0-1.0 how confident in this assessment\n"
            "- evidence: brief explanation of the comparison\n"
            "- details: any additional context"
        )

        try:
            result = await agenerate_json(role="head", prompt=prompt, temperature=0.1)
            if not isinstance(result, dict):
                raise ValueError("Invalid LLM response")

            return ComparisonResult(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                status=result.get("status", "unverifiable"),
                claimed_value=claim.claimed_value,
                actual_value=result.get("actual_value"),
                confidence=float(result.get("confidence", 0.0)),
                evidence=result.get("evidence", ""),
                details=result.get("details", ""),
            )
        except Exception as exc:
            logger.warning("LLM comparison failed: %s", exc)
            return ComparisonResult(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                status="unverifiable",
                claimed_value=claim.claimed_value,
                actual_value=None,
                confidence=0.0,
                evidence=f"Comparison error: {exc}",
            )

    async def compare_batch(
        self,
        claims: list[EmpiricalClaim],
        results: list[ExecutionResult],
    ) -> list[ComparisonResult]:
        """Compare multiple claims against their execution results."""
        result_map = {r.claim_id: r for r in results}
        comparisons: list[ComparisonResult] = []

        for claim in claims:
            exec_result = result_map.get(claim.claim_id)
            if exec_result is None:
                comparisons.append(ComparisonResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    status="unverifiable",
                    claimed_value=claim.claimed_value,
                    actual_value=None,
                    confidence=0.0,
                    evidence="No execution result available",
                ))
                continue
            comparison = await self.compare(claim, exec_result)
            comparisons.append(comparison)

        passes = sum(1 for c in comparisons if c.status == "pass")
        logger.info(
            "ResultComparator: %d/%d claims verified (pass: %d, fail: %d, partial: %d)",
            len(comparisons), len(claims),
            passes,
            sum(1 for c in comparisons if c.status == "fail"),
            sum(1 for c in comparisons if c.status == "partial"),
        )
        return comparisons
