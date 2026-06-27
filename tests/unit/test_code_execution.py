import pytest
import os
import shutil
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from research_agent.orchestration.nodes.code_execution import code_execution_node


@pytest.mark.asyncio
async def test_code_execution_no_blocks(tmp_path):
    state = {
        "run_id": "test_run_1",
        "topic": "Testing No Code",
        "latex_main": "This is a LaTeX document without any code.",
        "combined_sections": [],
        "artifact_root": str(tmp_path),
        "run_warnings": [],
        "math_verification_report": "Math is good."
    }
    
    result = await code_execution_node(state)
    assert result["phase"] == "completed"

    assert len(result["run_warnings"]) == 0


@pytest.mark.asyncio
async def test_code_execution_with_minted_block(tmp_path):
    latex_content = (
        "\\begin{minted}{python}\n"
        "x = 5\n"
        "y = 10\n"
        "print(f'sum={x+y}')\n"
        "\\end{minted}"
    )
    
    state = {
        "run_id": "test_run_2",
        "topic": "Testing Minted Code",
        "latex_main": latex_content,
        "combined_sections": [],
        "artifact_root": str(tmp_path),
        "run_warnings": [],
        "math_verification_report": "Math check complete."
    }
    
    result = await code_execution_node(state)
    assert "sum=15" in result["math_verification_report"]
    assert len(result["run_warnings"]) == 0
    
    run_dir = tmp_path / "test_run_2"
    assert (run_dir / "scratch_verify.py").exists()
    assert (run_dir / "runnable_code.ipynb").exists()
    
    notebook = json.loads((run_dir / "runnable_code.ipynb").read_text(encoding="utf-8"))
    assert len(notebook["cells"]) == 2
    assert notebook["cells"][1]["cell_type"] == "code"


@pytest.mark.asyncio
async def test_code_execution_with_failing_block(tmp_path):
    latex_content = (
        "\\begin{minted}{python}\n"
        "raise ValueError('Verification Failure!')\n"
        "\\end{minted}"
    )
    
    state = {
        "run_id": "test_run_3",
        "topic": "Testing Failing Code",
        "latex_main": latex_content,
        "combined_sections": [],
        "artifact_root": str(tmp_path),
        "run_warnings": [],
        "math_verification_report": ""
    }
    
    result = await code_execution_node(state)
    assert "Verification Status:** ❌ FAILED" in result["math_verification_report"]
    assert any("code_executor:execution_failed" in w for w in result["run_warnings"])
