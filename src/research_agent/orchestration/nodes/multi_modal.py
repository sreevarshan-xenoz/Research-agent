"""Multi-modal analysis node for the orchestration graph (P22).

This node runs the full multi-modal extraction pipeline on paper PDFs
when they are available, extracting figures, tables, equations, and
chart descriptions. The extracted content is stored in the graph state.
"""

from __future__ import annotations

import logging
from pathlib import Path

from research_agent.orchestration.state import GraphState

logger = logging.getLogger(__name__)


async def multi_modal_node(state: GraphState) -> dict:
    """Run multi-modal extraction on available paper PDFs.

    Checks the graph state for paper PDF paths (from ArXiv intake or
    user uploads) and runs figure extraction, table parsing, equation
    extraction, and chart-to-text generation.

    Args:
        state: Current GraphState with paper PDFs in task_findings.

    Returns:
        Dict with multi_modal data to merge into state.
    """
    from research_agent.config import load_settings
    settings = load_settings()

    multi_modal_cfg = settings.multi_modal
    if not multi_modal_cfg.enabled:
        logger.info("Multi-modal analysis disabled by config")
        return {"phase": state.get("phase", "multi_modal_skipped")}

    # Collect PDFs from task findings (ArXiv downloads, uploaded PDFs)
    pdf_paths = _collect_pdfs(state)

    if not pdf_paths:
        logger.info("No PDFs available for multi-modal analysis")
        return {"phase": state.get("phase", "multi_modal_skipped")}

    from research_agent.multi_modal.pipeline import run_multi_modal_pipeline

    artifact_dir = Path(state.get("artifact_dir", state.get("artifact_root", ".runtime/artifacts")))
    mm_dir = artifact_dir / "multi_modal"
    mm_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    for pdf_path in pdf_paths[:3]:  # Limit to first 3 PDFs
        try:
            result = await run_multi_modal_pipeline(
                pdf_path=pdf_path,
                output_dir=mm_dir / pdf_path.stem,
                extract_figures=multi_modal_cfg.extract_figures,
                extract_tables=multi_modal_cfg.extract_tables,
                extract_equations=multi_modal_cfg.extract_equations,
                generate_chart_descriptions=multi_modal_cfg.generate_chart_descriptions,
                max_figures=multi_modal_cfg.max_figures,
                max_tables=multi_modal_cfg.max_tables,
                max_equations=multi_modal_cfg.max_equations,
            )
            all_results.append(result.to_dict())
            logger.info(
                "Multi-modal extraction for %s: %d figures, %d tables, %d equations",
                pdf_path.name,
                result.figure_count,
                result.table_count,
                result.equation_count,
            )
        except Exception as exc:
            logger.error("Multi-modal extraction failed for %s: %s", pdf_path, exc)
            all_results.append({"error": str(exc), "pdf": str(pdf_path)})

    return {
        "multi_modal_results": all_results,
        "phase": "multi_modal_complete",
    }


def _collect_pdfs(state: GraphState) -> list[Path]:
    """Collect PDF file paths from the graph state.

    Looks in artifact directories for downloaded/uploaded PDFs.
    Only returns paths that actually exist on the local filesystem.
    Skips HTTP URL-based entries from task_findings.
    """
    pdf_paths: list[Path] = []

    # Check artifact directories for downloaded PDFs
    artifact_dir = Path(state.get("artifact_dir", state.get("artifact_root", ".runtime/artifacts")))
    search_dirs = [artifact_dir]

    # Also check data/raw for uploaded PDFs
    data_raw = Path("data/raw")
    if data_raw.exists():
        search_dirs.append(data_raw)

    for search_dir in search_dirs:
        if search_dir.exists():
            for pdf_file in search_dir.rglob("*.pdf"):
                if pdf_file.exists() and pdf_file not in pdf_paths:
                    pdf_paths.append(pdf_file)

    return pdf_paths
