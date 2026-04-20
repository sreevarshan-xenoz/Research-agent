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
    summary: dict[str, Any],
    template_name: str,
) -> str:
    settings = load_settings()
    run_dir = Path(artifact_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "main.tex").write_text(main_tex, encoding="utf-8")
    (run_dir / "references.bib").write_text(bibtex, encoding="utf-8")
    (run_dir / "compile_instructions.md").write_text(
        build_compile_instructions(template_name),
        encoding="utf-8",
    )
    
    # v2: PDF Compilation
    if settings.features.pdf_export:
        pdf_path = _compile_pdf_with_tectonic(run_dir)
        if pdf_path:
            summary["pdf_artifact"] = "main.pdf"

    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    return str(run_dir)
