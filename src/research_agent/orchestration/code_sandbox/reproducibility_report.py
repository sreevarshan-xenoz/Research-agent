from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from research_agent.orchestration.code_sandbox.claim_extractor import EmpiricalClaim
from research_agent.orchestration.code_sandbox.result_comparator import ComparisonResult
from research_agent.orchestration.code_sandbox.execution_engine import ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class ReproducibilityReport:
    """Structured reproducibility report for the entire paper."""
    topic: str
    total_claims: int = 0
    verified_passed: int = 0
    verified_failed: int = 0
    verified_partial: int = 0
    unverifiable: int = 0
    overall_score: float = 0.0  # 0.0–1.0
    items: list[dict[str, Any]] = field(default_factory=list)
    markdown_report: str = ""


class ReproducibilityReportGenerator:
    """Generates structured reproducibility reports from comparison results."""

    def generate(
        self,
        topic: str,
        claims: list[EmpiricalClaim],
        execution_results: list[ExecutionResult],
        comparisons: list[ComparisonResult],
    ) -> ReproducibilityReport:
        """Generate a comprehensive reproducibility report."""
        exec_map = {r.claim_id: r for r in execution_results}

        items: list[dict[str, Any]] = []
        for comp in comparisons:
            claim = next((c for c in claims if c.claim_id == comp.claim_id), None)
            exec_result = exec_map.get(comp.claim_id)

            items.append({
                "claim_id": comp.claim_id,
                "claim_text": comp.claim_text,
                "section_title": claim.section_title if claim else "Unknown",
                "claimed_value": comp.claimed_value,
                "actual_value": comp.actual_value,
                "status": comp.status,
                "confidence": comp.confidence,
                "evidence": comp.evidence,
                "details": comp.details,
                "duration_seconds": exec_result.sandbox_result.duration_seconds if exec_result else 0,
                "sandbox_type": exec_result.sandbox_result.sandbox_type if exec_result else "N/A",
                "dependencies": exec_result.dependencies if exec_result else [],
            })

        total = len(comparisons)
        passed = sum(1 for c in comparisons if c.status == "pass")
        failed = sum(1 for c in comparisons if c.status == "fail")
        partial = sum(1 for c in comparisons if c.status == "partial")
        unverifiable = sum(1 for c in comparisons if c.status == "unverifiable")

        # Overall score: weighted average
        if total > 0:
            score = (passed * 1.0 + partial * 0.5) / total
        else:
            score = 0.0

        markdown = self._generate_markdown(
            topic, passed, failed, partial, unverifiable,
            total, score, items,
        )

        return ReproducibilityReport(
            topic=topic,
            total_claims=total,
            verified_passed=passed,
            verified_failed=failed,
            verified_partial=partial,
            unverifiable=unverifiable,
            overall_score=round(score, 3),
            items=items,
            markdown_report=markdown,
        )

    def _generate_markdown(
        self,
        topic: str,
        passed: int,
        failed: int,
        partial: int,
        unverifiable: int,
        total: int,
        score: float,
        items: list[dict[str, Any]],
    ) -> str:
        """Generate a markdown reproducibility report."""
        lines: list[str] = []
        lines.append(f"# Reproducibility Report: {topic}")
        lines.append("")
        lines.append("**Generated:** Automated via Code Sandbox (P24)")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Claims | {total} |")
        lines.append(f"| ✅ Verified (Pass) | {passed} |")
        lines.append(f"| ❌ Verified (Fail) | {failed} |")
        lines.append(f"| 🟡 Verified (Partial) | {partial} |")
        lines.append(f"| ⬜ Unverifiable | {unverifiable} |")
        lines.append(f"| Overall Score | {score:.1%} |")
        lines.append("")

        if score >= 0.8:
            lines.append("**Overall Verdict: ✅ Strong reproducibility**")
        elif score >= 0.5:
            lines.append("**Overall Verdict: 🟡 Partial reproducibility**")
        else:
            lines.append("**Overall Verdict: ❌ Poor reproducibility**")
        lines.append("")

        # Per-claim details
        lines.append("## Per-Claim Results")
        lines.append("")

        for item in items:
            status_emoji = {
                "pass": "✅",
                "fail": "❌",
                "partial": "🟡",
                "unverifiable": "⬜",
            }.get(item["status"], "❓")

            lines.append(f"### {status_emoji} {item['claim_text'][:120]}")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            lines.append(f"| **Section** | {item['section_title']} |")
            lines.append(f"| **Status** | {item['status'].upper()} |")
            lines.append(f"| **Claimed Value** | {item['claimed_value'] or 'N/A'} |")
            lines.append(f"| **Actual Value** | {item['actual_value'] or 'N/A'} |")
            lines.append(f"| **Confidence** | {item['confidence']:.0%} |")
            lines.append(f"| **Runtime** | {item['duration_seconds']:.1f}s |")
            lines.append(f"| **Sandbox** | {item['sandbox_type']} |")
            if item["dependencies"]:
                lines.append(f"| **Dependencies** | {', '.join(item['dependencies'])} |")
            lines.append("")
            if item["evidence"]:
                lines.append(f"**Evidence:** {item['evidence']}")
                lines.append("")
            if item["details"]:
                lines.append(f"**Details:** {item['details']}")
                lines.append("")
            lines.append("---")
            lines.append("")

        lines.append("## Methodology")
        lines.append("")
        lines.append("This report was generated by the Verified Code Execution Sandbox (P24):")
        lines.append("")
        lines.append("1. **Claim Extraction**: LLM identifies empirical claims from paper sections")
        lines.append("2. **Code Generation**: LLM generates verification Python code per claim")
        lines.append("3. **Execution**: Code runs in isolated Docker sandbox (or subprocess fallback)")
        lines.append("4. **Comparison**: Results compared to claimed values (numerical + LLM-based)")
        lines.append("5. **Report**: Structured per-claim pass/fail/partial with evidence")
        lines.append("")

        return "\n".join(lines)
