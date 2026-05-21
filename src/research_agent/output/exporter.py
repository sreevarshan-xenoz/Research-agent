from __future__ import annotations

import json
import subprocess
import shutil
from pathlib import Path
from typing import Any

from research_agent.output.latex.renderer import build_compile_instructions
from research_agent.config import load_settings


def _compile_pdf_with_tectonic(run_dir: Path) -> str | None:
    """Attempts to compile main.tex to main.pdf using tectonic."""
    if not shutil.which("tectonic"):
        return None
    
    try:
        # Tectonic handles bibtex automatically if needed
        subprocess.run(
            ["tectonic", "main.tex"], 
            cwd=run_dir, 
            check=True, 
            capture_output=True,
            timeout=120
        )
        pdf_path = run_dir / "main.pdf"
        if pdf_path.exists():
            return str(pdf_path)
    except Exception:
        pass
    return None


def export_run_artifacts(
    *,
    artifact_root: str,
    run_id: str,
    main_tex: str,
    bibtex: str,
    presentation_tex: str | None = None,
    future_research_agenda: str | None = None,
    comparison_table: str | None = None,
    peer_review_report: str | None = None,
    knowledge_graph: dict[str, Any] | None = None,
    bias_report: str | None = None,
    summary: dict[str, Any],
    template_name: str,
) -> str:
    settings = load_settings()
    run_dir = Path(artifact_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "main.tex").write_text(main_tex, encoding="utf-8")
    (run_dir / "references.bib").write_text(bibtex, encoding="utf-8")
    if presentation_tex:
        (run_dir / "presentation.tex").write_text(presentation_tex, encoding="utf-8")
    if future_research_agenda:
        (run_dir / "future_agenda.md").write_text(future_research_agenda, encoding="utf-8")
    if comparison_table:
        (run_dir / "comparison_table.tex").write_text(comparison_table, encoding="utf-8")
    if peer_review_report:
        (run_dir / "peer_review.md").write_text(peer_review_report, encoding="utf-8")
    if knowledge_graph:
        (run_dir / "knowledge_graph.json").write_text(
            json.dumps(knowledge_graph, indent=2, ensure_ascii=True),
            encoding="utf-8"
        )
    if bias_report:
        (run_dir / "bias_report.md").write_text(bias_report, encoding="utf-8")
    (run_dir / "compile_instructions.md").write_text(
        build_compile_instructions(template_name),
        encoding="utf-8",
    )
    
    # v2: PDF Compilation
    if settings.features.pdf_export:
        pdf_path = _compile_pdf_with_tectonic(run_dir)
        if pdf_path:
            summary["pdf_artifact"] = "main.pdf"

    summary["overleaf_url"] = build_overleaf_import_url(
        main_tex=main_tex,
        bibtex=bibtex,
        project_name=f"Research: {summary.get('topic', 'Untitled')}"
    )

    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    return str(run_dir)
