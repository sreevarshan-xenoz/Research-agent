import json
import sys
import time
import threading
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState
from research_agent.config import load_settings
from research_agent.tools import build_tool_registry


import asyncio

async def main():
    print("=" * 60)
    print("  Research Agent -- Full Flow Test")
    print("=" * 60)

    settings = load_settings()
    tool_registry = build_tool_registry(settings)
    interrupt_signal = threading.Event()

    # --- Test 1: Clarification Detection ---
    print("\n[Test 1] Ambiguous topic -> should trigger clarification")
    state1 = WorkflowState(
        run_id="test-clarify-001",
        topic="AI",
        template="ieee-2col",
        depth="quick",
        autonomy_mode="hybrid",
        max_runtime_minutes=5,
        max_cost_usd=1.0,
        max_iterations=1,
        started_at=time.time(),
        interrupted=False,
        artifact_root="./artifacts",
    )
    result1 = await run_graph(state1, registry=tool_registry)
    print(f"  Phase: {result1.phase}")
    print(f"  Needs clarification: {result1.needs_clarification}")
    print(f"  Questions: {result1.clarification_questions}")
    assert result1.phase == "awaiting_user_clarification", f"Expected clarification, got {result1.phase}"
    print("  [PASS] Clarification correctly triggered\n")

    # --- Test 2: Full pipeline with specific (non-ambiguous) topic ---
    print("[Test 2] Specific topic -> full pipeline execution")
    topic = (
        "Comparing CRISPR-Cas9 gene editing efficiency across "
        "different delivery mechanisms in therapeutic applications"
    )
    state2 = WorkflowState(
        run_id="test-full-001",
        topic=topic,
        template="ieee-2col",
        depth="quick",
        autonomy_mode="hybrid",
        max_runtime_minutes=5,
        max_cost_usd=1.0,
        max_iterations=1,
        started_at=time.time(),
        interrupted=False,
        artifact_root="./artifacts",
    )
    t0 = time.time()
    result2 = await run_graph(state2, registry=tool_registry)
    elapsed = time.time() - t0

    print(f"  Phase: {result2.phase}")
    print(f"  Stop reason: {result2.stop_reason}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Tasks: {len(result2.tasks)}")
    for t in result2.tasks:
        print(f"    [{t.status:>8}] {t.task_id}: {t.title}")

    print(f"\n  Section confidence:")
    for tid, conf in result2.section_confidence.items():
        print(f"    {tid}: {conf:.3f}")

    print(f"\n  Critic notes ({len(result2.critic_notes)}):")
    for note in result2.critic_notes:
        print(f"    - {note}")

    print(f"\n  Combined sections: {len(result2.combined_sections)}")
    print(f"  Citations: {len(result2.citations)}")
    print(f"  Warnings: {len(result2.run_warnings)}")
    for w in result2.run_warnings[:10]:
        print(f"    [WARN] {w}")

    print(f"\n  Artifact dir: {result2.artifact_dir}")

    # Check LaTeX output
    if result2.latex_main:
        print(f"  LaTeX length: {len(result2.latex_main)} chars")
        print(f"  LaTeX preview (first 300 chars):")
        print("  " + result2.latex_main[:300].replace("\n", "\n  "))
    else:
        print("  [WARN] No LaTeX generated!")

    # Check BibTeX
    if result2.bibtex:
        print(f"\n  BibTeX length: {len(result2.bibtex)} chars")
        print(f"  BibTeX preview (first 200 chars):")
        print("  " + result2.bibtex[:200].replace("\n", "\n  "))
    else:
        print("  [WARN] No BibTeX generated!")

    # Verify artifacts on disk
    from pathlib import Path
    if result2.artifact_dir:
        art_dir = Path(result2.artifact_dir)
        expected_files = ["main.tex", "references.bib", "compile_instructions.md", "summary.json"]
        for f in expected_files:
            file_path = art_dir / f
            exists = file_path.exists()
            size = file_path.stat().st_size if exists else 0
            status = "[OK]" if exists else "[MISSING]"
            print(f"  {status} {f} ({size} bytes)")

        # Parse summary.json
        summary_path = art_dir / "summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            print(f"\n  Summary JSON keys: {list(summary.keys())}")
    else:
        print("  [FAIL] No artifact dir -- export likely failed")

    # Verify key assertions
    errors = []
    if not result2.tasks:
        errors.append("No tasks were created")
    if not any(t.status == "complete" for t in result2.tasks):
        errors.append("No tasks completed")
    if not result2.latex_main:
        errors.append("No LaTeX output")
    if not result2.bibtex:
        errors.append("No BibTeX output")
    if result2.phase not in ("completed", "validation_failed"):
        errors.append(f"Unexpected final phase: {result2.phase}")
    if not result2.artifact_dir:
        errors.append("Artifact dir not set")

    print("\n" + "=" * 60)
    if errors:
        print("  ISSUES FOUND:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  ALL CHECKS PASSED -- Full pipeline executed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
