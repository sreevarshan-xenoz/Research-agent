from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_agent.output.latex.renderer import build_compile_instructions


def export_run_artifacts(
    *,
    artifact_root: str,
    run_id: str,
    main_tex: str,
    bibtex: str,
    summary: dict[str, Any],
    template_name: str,
) -> str:
    run_dir = Path(artifact_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "main.tex").write_text(main_tex, encoding="utf-8")
    (run_dir / "references.bib").write_text(bibtex, encoding="utf-8")
    (run_dir / "compile_instructions.md").write_text(
        build_compile_instructions(template_name),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    return str(run_dir)
