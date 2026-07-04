from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.orchestration.code_sandbox.sandbox import DockerSandbox, SandboxConfig
from research_agent.orchestration.code_sandbox.claim_extractor import ClaimExtractor
from research_agent.orchestration.code_sandbox.code_generator import CodeGenerator
from research_agent.orchestration.code_sandbox.execution_engine import ExecutionEngine
from research_agent.orchestration.code_sandbox.result_comparator import ResultComparator
from research_agent.orchestration.code_sandbox.reproducibility_report import ReproducibilityReportGenerator

if TYPE_CHECKING:
    from research_agent.orchestration.code_sandbox.claim_extractor import EmpiricalClaim
    from research_agent.orchestration.code_sandbox.execution_engine import ExecutionResult
    from research_agent.orchestration.code_sandbox.result_comparator import ComparisonResult
    from research_agent.orchestration.code_sandbox.reproducibility_report import ReproducibilityReport

logger = logging.getLogger(__name__)


async def code_sandbox_node(state: GraphState) -> dict:
    """Orchestrates the verified code execution pipeline (P24).

    Pipeline:
    1. Extract empirical claims from paper sections
    2. Generate verification code for each claim
    3. Execute code in sandbox (Docker with subprocess fallback)
    4. Compare results against claimed values
    5. Generate structured reproducibility report
    6. Export report and results to run directory
    """
    await apublish_progress(
        agent="Code Sandbox (P24)",
        status="running",
        detail="Initializing verification pipeline",
        message="Verifying empirical claims via code execution",
    )

    topic = state.get("topic", "")
    run_id = state["run_id"]
    artifact_root = state.get("artifact_root", ".runtime/artifacts")
    run_dir = Path(artifact_root) / run_id
    combined_sections = state.get("combined_sections", [])
    latex_main = state.get("latex_main", "")

    # Build section list from both combined_sections and latex_main
    sections = list(combined_sections)
    if latex_main and not sections:
        sections = [{"title": "Main Paper", "content": latex_main}]

    if not sections:
        await apublish_progress(
            agent="Code Sandbox (P24)",
            status="complete",
            detail="No paper sections found",
            message="Verification skipped — no content to analyze",
        )
        return {"phase": "completed"}

    run_dir.mkdir(parents=True, exist_ok=True)

    # Load settings
    from research_agent.config import load_settings
    settings = load_settings()
    sandbox_enabled = getattr(getattr(settings, "code_sandbox", None), "enabled", True)

    if not sandbox_enabled:
        await apublish_progress(
            agent="Code Sandbox (P24)",
            status="complete",
            detail="Sandbox disabled in config",
            message="Verification skipped",
        )
        return {"phase": "completed"}

    # Phase 1: Extract claims
    await apublish_progress(
        agent="Code Sandbox",
        status="running",
        detail="Analyzing paper sections",
        message="Extracting empirical claims",
    )
    extractor = ClaimExtractor(
        min_verification_potential=getattr(
            getattr(settings, "code_sandbox", None), "min_verification_potential", 0.3
        ),
    )
    claims = await extractor.extract_claims(sections, topic)
    empirical_claims_data = [_claim_to_dict(c) for c in claims]

    if not claims:
        await apublish_progress(
            agent="Code Sandbox",
            status="complete",
            detail="No verifiable claims found",
            message="Verification skipped",
        )
        return {
            "empirical_claims": empirical_claims_data,
            "phase": "completed",
        }

    # Phase 2: Generate verification code
    await apublish_progress(
        agent="Code Sandbox",
        status="running",
        detail=f"Generating code for {len(claims)} claims",
        message="Generating verification scripts",
    )
    code_gen = CodeGenerator()
    verification_codes = await code_gen.generate_codes(claims, paper_context=latex_main[:5000])

    if not verification_codes:
        await apublish_progress(
            agent="Code Sandbox",
            status="complete",
            detail="Code generation failed",
            message="Verification failed — could not generate code",
        )
        return {
            "empirical_claims": empirical_claims_data,
            "run_warnings": state.get("run_warnings", []) + ["code_sandbox:code_generation_failed"],
            "phase": "completed",
        }

    # Phase 3: Execute code
    await apublish_progress(
        agent="Code Sandbox",
        status="running",
        detail=f"Executing {len(verification_codes)} scripts",
        message="Running verification code",
    )
    sandbox_config = SandboxConfig(
        container_timeout=getattr(getattr(settings, "code_sandbox", None), "container_timeout", 60),
        memory_limit_mb=getattr(getattr(settings, "code_sandbox", None), "memory_limit_mb", 512),
    )
    sandbox = DockerSandbox(sandbox_config)
    engine = ExecutionEngine(sandbox)
    execution_results = await engine.execute_batch(verification_codes)

    # Phase 4: Compare results
    await apublish_progress(
        agent="Code Sandbox",
        status="running",
        detail="Analyzing results",
        message="Comparing results to claimed values",
    )
    comparator = ResultComparator()
    comparisons = await comparator.compare_batch(claims, execution_results)

    # Phase 5: Generate report
    await apublish_progress(
        agent="Code Sandbox",
        status="running",
        detail="Generating report",
        message="Creating reproducibility report",
    )
    report_gen = ReproducibilityReportGenerator()
    report = report_gen.generate(topic, claims, execution_results, comparisons)

    # Phase 6: Export results
    _export_results(run_dir, report, empirical_claims_data, execution_results, comparisons)

    await apublish_progress(
        agent="Code Sandbox",
        status="complete",
        detail=f"Reproducibility score: {report.overall_score:.1%}",
        message="Verification complete",
    )

    # Build code verification items for state
    code_verification_items = [
        {
            "claim_id": c.claim_id,
            "claim_text": c.claim_text,
            "status": c.status,
            "claimed_value": c.claimed_value,
            "actual_value": c.actual_value,
            "confidence": c.confidence,
        }
        for c in comparisons
    ]

    run_warnings = list(state.get("run_warnings", []))
    for c in comparisons:
        if c.status == "fail":
            run_warnings.append(f"code_sandbox:claim_failed:{c.claim_id}:{c.claim_text[:80]}")

    return {
        "empirical_claims": empirical_claims_data,
        "code_verification_items": code_verification_items,
        "code_reproducibility_report": report.markdown_report,
        "run_warnings": run_warnings,
        "phase": "completed",
    }


def _claim_to_dict(claim: EmpiricalClaim) -> dict:
    return {
        "claim_id": claim.claim_id,
        "claim_text": claim.claim_text,
        "section_title": claim.section_title,
        "metric": claim.metric,
        "dataset": claim.dataset,
        "baseline": claim.baseline,
        "claimed_value": claim.claimed_value,
        "verification_potential": claim.verification_potential,
        "context": claim.context,
    }


def _export_results(
    run_dir: Path,
    report: ReproducibilityReport,
    empirical_claims: list[dict],
    execution_results: list[ExecutionResult],
    comparisons: list[ComparisonResult],
) -> None:
    """Export all results to the run directory."""
    # Main report
    try:
        (run_dir / "reproducibility_report.md").write_text(
            report.markdown_report, encoding="utf-8"
        )
    except Exception as e:
        logger.error("Failed to write reproducibility_report.md: %s", e)

    # Claims JSON
    try:
        claims_data = []
        for comp in comparisons:
            exec_result = next(
                (r for r in execution_results if r.claim_id == comp.claim_id),
                None,
            )
            claims_data.append({
                "claim_id": comp.claim_id,
                "claim_text": comp.claim_text,
                "status": comp.status,
                "claimed_value": comp.claimed_value,
                "actual_value": comp.actual_value,
                "confidence": comp.confidence,
                "evidence": comp.evidence,
                "duration_seconds": exec_result.sandbox_result.duration_seconds if exec_result else 0,
                "sandbox_type": exec_result.sandbox_result.sandbox_type if exec_result else "N/A",
            })
        (run_dir / "code_verification_results.json").write_text(
            json.dumps({"items": claims_data, "overall_score": report.overall_score, "total_claims": report.total_claims}, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.error("Failed to write code_verification_results.json: %s", e)

    # Per-claim generated scripts
    scripts_dir = run_dir / "verification_scripts"
    try:
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for er in execution_results:
            script_path = scripts_dir / f"{er.claim_id}.py"
            script_path.write_text(er.code, encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write verification scripts: %s", e)

    # Claims summary
    try:
        (run_dir / "empirical_claims.json").write_text(
            json.dumps(empirical_claims, indent=2), encoding="utf-8"
        )
    except Exception as e:
        logger.error("Failed to write empirical_claims.json: %s", e)
