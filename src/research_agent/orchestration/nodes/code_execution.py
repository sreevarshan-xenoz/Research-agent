from __future__ import annotations
from typing import Any
import asyncio
import json
import logging
from pathlib import Path
import re
import subprocess
import sys

from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState

logger = logging.getLogger(__name__)


async def code_execution_node(state: GraphState) -> dict:
    """Extracts python code blocks from generated LaTeX main or sections,
    runs it, verifies reproducibility, updates math_verification_report,
    and generates runnable_code.ipynb notebook in the run directory.
    """
    await apublish_progress(
        agent="Code Executor",
        status="running",
        detail="Extracting code blocks",
        message="Verifying code reproducibility",
    )

    latex_main = state.get("latex_main", "")
    combined_sections = state.get("combined_sections", [])
    run_id = state["run_id"]
    artifact_root = state.get("artifact_root", ".runtime/artifacts")
    run_dir = Path(artifact_root) / run_id
    
    content_to_search = latex_main
    if not content_to_search and combined_sections:
        content_to_search = "\n".join([sec.get("content", "") for sec in combined_sections if isinstance(sec, dict)])

    code_blocks = []
    if content_to_search:
        # Minted python blocks
        minted_blocks = re.findall(r"\\begin\{minted\}\{python\}(.*?)\\end\{minted\}", content_to_search, re.DOTALL)
        code_blocks.extend([b.strip() for b in minted_blocks if b.strip()])

        # Lstlisting blocks with python
        lst_blocks = re.findall(r"\\begin\{lstlisting\}(?:\[.*?language=Python.*?\])?(.*?)\\end\{lstlisting\}", content_to_search, re.DOTALL)
        code_blocks.extend([b.strip() for b in lst_blocks if b.strip()])

        # Markdown blocks
        md_blocks = re.findall(r"```python(.*?)```", content_to_search, re.DOTALL)
        code_blocks.extend([b.strip() for b in md_blocks if b.strip()])

    run_warnings = list(state.get("run_warnings", []))
    math_report = state.get("math_verification_report", "") or ""

    if not code_blocks:
        await apublish_progress(
            agent="Code Executor",
            status="complete",
            detail="No code blocks found",
            message="Verification complete",
        )
        return {
            "phase": "completed",
            "run_warnings": run_warnings
        }

    full_script = "\n\n# --- Extracted Code Block ---\n\n".join(code_blocks)
    
    run_dir.mkdir(parents=True, exist_ok=True)
    script_path = run_dir / "scratch_verify.py"
    
    try:
        script_path.write_text(full_script, encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to write scratch script: {e}")

    await apublish_progress(
        agent="Code Executor",
        status="running",
        detail="Executing code verification",
        message="Verifying computations",
    )

    stdout = ""
    stderr = ""
    success = True
    error_message = ""

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                success = False
                error_message = f"Execution exited with code {proc.returncode}"
        except asyncio.TimeoutError:
            proc.kill()
            success = False
            error_message = "Execution timed out after 15.0 seconds"
    except Exception as e:
        success = False
        error_message = f"Subprocess start error: {str(e)}"

    report_addition = (
        "\n\n## Code Execution & Reproducibility Verification Report\n\n"
        f"- **Verification Status:** {'✅ PASSED' if success else '❌ FAILED'}\n"
        f"- **Python Version:** {sys.version.split()[0]}\n"
    )
    if error_message:
        report_addition += f"- **Error Detail:** {error_message}\n"
        run_warnings.append(f"code_executor:execution_failed:{error_message}")
        
    report_addition += "\n### Code Output:\n```txt\n"
    if stdout.strip():
        report_addition += stdout
    else:
        report_addition += "[No output printed to stdout]"
    report_addition += "\n```\n"

    if stderr.strip():
        report_addition += f"\n### Errors/Warnings captured:\n```txt\n{stderr}\n```\n"

    math_report += report_addition

    try:
        (run_dir / "math_verification.md").write_text(math_report, encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to write math_verification.md: {e}")

    notebook: dict[str, Any] = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    f"# Reproducibility Code for: {state.get('topic', 'Untitled Topic')}\n\n",
                    "This notebook contains the code blocks extracted from the generated research paper."
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2
    }

    for idx, code in enumerate(code_blocks):
        notebook["cells"].append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [line + "\n" for line in code.splitlines()]
        })

    try:
        ipynb_path = run_dir / "runnable_code.ipynb"
        ipynb_path.write_text(json.dumps(notebook, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to write notebook: {e}")

    await apublish_progress(
        agent="Code Executor",
        status="complete",
        detail="Reproducibility verified",
        message="Notebook and report created",
    )

    return {
        "math_verification_report": math_report,
        "run_warnings": run_warnings,
        "phase": "completed"
    }
