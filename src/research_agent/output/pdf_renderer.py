from __future__ import annotations

import logging
import subprocess
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def get_pdf_path(run_dir: Path) -> str | None:
    pdf_path = run_dir / "main.pdf"
    if pdf_path.exists():
        return str(pdf_path)
    return None


def compile_pdf(run_dir: Path) -> str | None:
    pdf_path = compile_with_tectonic(run_dir)
    if pdf_path:
        return pdf_path
    pdf_path = compile_with_docker(run_dir)
    if pdf_path:
        return pdf_path
    return None


def compile_with_tectonic(run_dir: Path) -> str | None:
    if not shutil.which("tectonic"):
        return None
    try:
        subprocess.run(
            ["tectonic", "main.tex"],
            cwd=run_dir,
            check=True,
            capture_output=True,
            timeout=120,
        )
        pdf_path = run_dir / "main.pdf"
        if pdf_path.exists():
            return str(pdf_path)
    except Exception as e:
        logger.warning("tectonic compilation failed: %s", e)
    return None


def compile_with_docker(run_dir: Path) -> str | None:
    if not shutil.which("docker"):
        return None
    try:
        subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{run_dir.resolve()}:/workspace",
                "research-agent-tex", "main.tex",
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
        pdf_path = run_dir / "main.pdf"
        if pdf_path.exists():
            return str(pdf_path)
    except Exception as e:
        logger.warning("docker compilation failed: %s", e)
    return None
