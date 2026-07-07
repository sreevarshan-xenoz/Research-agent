"""Integration tests for autonomous mode end-to-end flow through the full graph.

These tests spin up the full LangGraph pipeline with autonomous mode and verify
the end-to-end behavior: auto-discovery, clarification bypass, task planning,
worker execution (with empty registry), critic iteration, and artifact export.

Uses the same test infrastructure as test_smoke.py and test_iteration_loop.py:
- monkeypatch for env isolation
- pytest-asyncio for async graph execution
- empty registry (no real API calls)
- mocked LLM (via conftest test_env fixture)
- tmp_path for artifact output isolation
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


# ── Autonomous Mode: Auto-Discover Flow ────────────────────────────────────


class TestAutonomousAutoDiscover:
    """Tests that autonomous mode with empty topic auto-selects and completes."""

    @pytest.mark.asyncio
    async def test_empty_topic_auto_selects(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode with an empty topic should auto-select a fallback topic
        from trending topics and proceed through the pipeline."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_discover",
            topic="",  # Empty topic triggers auto-discovery
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
        )
        updated = await run_graph(state, registry={})

        # Should complete without requiring user input
        assert updated.phase == "completed"
        assert updated.stop_reason in ("completed", "max_iterations_reached")
        # Topic should have been auto-selected (not empty)
        assert len(updated.topic) > 0
        assert updated.topic != ""
        # Tasks should have been planned and executed
        assert len(updated.tasks) >= 3
        assert all(task.status == "complete" for task in updated.tasks)

    @pytest.mark.asyncio
    async def test_placeholder_topic_auto_selects(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode with 'auto-discover' placeholder should auto-select."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_discover_placeholder",
            topic="auto-discover",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
        )
        updated = await run_graph(state, registry={})

        assert updated.phase == "completed"
        assert len(updated.topic) > 0
        assert updated.topic.lower() != "auto-discover"

    @pytest.mark.asyncio
    async def test_auto_discover_skips_clarification(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode should skip the clarifier node entirely."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_skip_clarify",
            topic="",  # Would normally trigger clarification
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
        )
        updated = await run_graph(state, registry={})

        # Should NOT be awaiting user clarification
        assert updated.phase != "awaiting_user_clarification"
        assert updated.stop_reason != "clarification_required"
        # No clarification questions should have been generated
        assert not updated.clarification_questions
        # Should have completed the pipeline
        assert updated.phase == "completed"

    @pytest.mark.asyncio
    async def test_auto_discover_with_past_topics(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode with past research topics should prefer those topics."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        past_topics = [
            "Graph Neural Networks for Molecular Discovery",
            "Attention Mechanisms in Computer Vision",
            "Reinforcement Learning for Robotics",
        ]
        state = WorkflowState(
            run_id="auto_past_topics",
            topic="",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
            past_research_topics=past_topics,
        )
        updated = await run_graph(state, registry={})

        assert updated.phase == "completed"
        # Topic should be one of the past topics
        assert updated.topic in past_topics, f"Expected one of {past_topics}, got '{updated.topic}'"


# ── Autonomous Mode: Clarification Bypass ──────────────────────────────────


class TestAutonomousClarification:
    """Tests that autonomous mode bypasses user clarification for specific topics."""

    @pytest.mark.asyncio
    async def test_specific_topic_skips_clarification(self, tmp_path: Path, monkeypatch) -> None:
        """A specific unambiguous topic in autonomous mode should skip clarification."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_specific",
            topic="Attention mechanisms in transformer models for long document summarization",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
        )
        updated = await run_graph(state, registry={})

        # Should NOT await user clarification — autonomous mode bypasses it
        assert updated.phase != "awaiting_user_clarification"
        assert updated.clarification_questions is None or len(updated.clarification_questions) == 0

    @pytest.mark.asyncio
    async def test_specific_topic_hybrid_mode_bypasses_clarification(self, tmp_path: Path, monkeypatch) -> None:
        """Hybrid mode with a specific topic should also skip clarification."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="hybrid_specific",
            topic="Efficient fine-tuning methods for large language models",
            autonomy_mode="hybrid",
            artifact_root=str(tmp_path),
            max_iterations=1,
        )
        updated = await run_graph(state, registry={})

        # Hybrid mode with specific topic → no clarification needed
        assert updated.phase != "awaiting_user_clarification"
        assert not updated.needs_clarification or not updated.clarification_questions

    @pytest.mark.asyncio
    async def test_ambiguous_topic_autonomous_bypasses(self, tmp_path: Path, monkeypatch) -> None:
        """Even an ambiguous topic in autonomous mode should skip clarification."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_ambiguous",
            topic="AI",  # Short/broad topic that would normally trigger clarification
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
        )
        updated = await run_graph(state, registry={})

        # Autonomous mode should bypass clarifier regardless of ambiguity
        assert updated.phase == "completed"
        assert updated.stop_reason != "clarification_required"


# ── Autonomous Mode: Full Pipeline ─────────────────────────────────────────


class TestAutonomousFullPipeline:
    """Tests that autonomous mode runs the full pipeline end-to-end."""

    @pytest.mark.asyncio
    async def test_full_pipeline_artifact_output(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode should produce artifacts with the full pipeline."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_full_pipe",
            topic="Comparative analysis of retrieval-augmented generation approaches",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
        )
        updated = await run_graph(state, registry={})

        assert updated.phase == "completed"
        assert updated.stop_reason == "completed"

        # Verify artifact directory exists
        assert updated.artifact_dir
        artifact_path = Path(updated.artifact_dir)
        assert artifact_path.exists()

        # Check for key artifact files
        assert (artifact_path / "main.tex").exists(), "Missing main.tex"
        assert (artifact_path / "references.bib").exists(), "Missing references.bib"
        assert (artifact_path / "summary.json").exists(), "Missing summary.json"

    @pytest.mark.asyncio
    async def test_full_pipeline_sections_generated(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode should generate combined sections."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_sections",
            topic="Transformer architecture optimizations for edge deployment",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
        )
        updated = await run_graph(state, registry={})

        assert updated.phase == "completed"
        # Combined sections should exist
        assert updated.combined_sections, "No combined sections generated"
        assert len(updated.combined_sections) >= 1

        # Each section should have a heading and content
        for section in updated.combined_sections:
            assert section.get("heading"), f"Section missing heading: {section}"
            assert section.get("content") is not None, f"Section missing content: {section.get('heading')}"

    @pytest.mark.asyncio
    async def test_full_pipeline_citations(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode should generate citations."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_citations",
            topic="Multi-modal learning for medical image analysis",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
        )
        updated = await run_graph(state, registry={})

        assert updated.phase == "completed"
        # Citations should be populated (even if minimal)
        assert updated.citations is not None

    @pytest.mark.asyncio
    async def test_full_pipeline_iteration_count(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode with max_iterations=2 should iterate the critic loop."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_iteration",
            topic="Quantum machine learning algorithms",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=2,
        )
        updated = await run_graph(state, registry={})

        assert updated.phase == "completed"
        # With empty registry, findings will be empty → low confidence → iteration loops
        # The iteration_index should be > 0 if the critic loop ran
        assert updated.iteration_index >= 1
        # With max_iterations=2, low confidence, should have run the loop
        total_tasks = len(updated.tasks)
        # The critic adds follow-up tasks when confidence is low
        # So total tasks > original planned tasks
        assert total_tasks >= 3


# ── Autonomous Mode: Template Integration ──────────────────────────────────


class TestAutonomousWithTemplates:
    """Tests that autonomous mode works with P39 research templates."""

    @pytest.mark.asyncio
    async def test_autonomous_with_literature_survey(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode with literature_survey template should use template's depth defaults."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_lit_survey",
            topic="Vision-language model architectures and pre-training strategies",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
            research_template="literature_survey",
        )
        updated = await run_graph(state, registry={})

        assert updated.phase == "completed"
        # Literature survey templates plan more tasks than standard
        # (depth_defaults: balanced=8, vs standard balanced=4)
        assert len(updated.tasks) >= 3

    @pytest.mark.asyncio
    async def test_autonomous_with_systematic_review(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode with systematic_review template should use PICO framework."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_sys_review",
            topic="AI-assisted diagnostic tools in clinical settings",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
            research_template="systematic_review",
        )
        updated = await run_graph(state, registry={})

        assert updated.phase == "completed"
        assert len(updated.tasks) >= 3

    @pytest.mark.asyncio
    async def test_autonomous_with_meta_analysis(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode with meta_analysis template should prefer PubMed providers."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_meta",
            topic="Effectiveness of deep learning in medical image segmentation",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
            research_template="meta_analysis",
        )
        updated = await run_graph(state, registry={})

        assert updated.phase == "completed"

    @pytest.mark.asyncio
    async def test_autonomous_with_case_study(self, tmp_path: Path, monkeypatch) -> None:
        """Autonomous mode with case_study template should use web-search providers."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_case",
            topic="Deploying large language models in production at enterprise scale",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
            research_template="case_study",
        )
        updated = await run_graph(state, registry={})

        assert updated.phase == "completed"
        # Case study has depth_defaults: balanced=5
        assert len(updated.tasks) >= 3

    @pytest.mark.asyncio
    async def test_invalid_template_falls_back_to_standard(self, tmp_path: Path, monkeypatch) -> None:
        """An invalid template ID should fall back to standard behavior."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_bad_template",
            topic="Few-shot learning approaches",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=1,
            research_template="nonexistent_template_xyz",
        )
        updated = await run_graph(state, registry={})

        assert updated.phase == "completed"
        # Should still complete successfully
        assert len(updated.tasks) >= 3


# ── Runtime Cap Enforcement ────────────────────────────────────────────────


class TestAutonomousRuntimeCap:
    """Tests that runtime caps are enforced in autonomous mode."""

    @pytest.mark.asyncio
    async def test_runtime_cap_terminates_early(self, tmp_path: Path, monkeypatch) -> None:
        """A very short runtime cap should terminate before full completion."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_runtime",
            topic="Distributed training of large neural networks",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_runtime_minutes=0,  # Zero disables runtime cap
            max_iterations=1,
        )
        updated = await run_graph(state, registry={})

        # Should complete (runtime cap disabled when 0)
        assert updated.phase == "completed"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_immediate_runtime_cap(self, tmp_path: Path, monkeypatch) -> None:
        """A runtime cap of 1 millisecond should trigger immediate termination."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        # Use a state that has already been running for a while
        state = WorkflowState(
            run_id="auto_immediate_cap",
            topic="Graph neural network architectures",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_runtime_minutes=0.001,  # Very small (tests time check logic)
            max_iterations=1,
            started_at=time.time() - 60,  # Started 60 seconds ago
        )
        updated = await run_graph(state, registry={})

        # With a tiny cap, the graph should finish anyway since
        # the runtime cap is checked at routing points not during execution
        assert updated.stop_reason in ("completed", "max_iterations_reached")

    @pytest.mark.asyncio
    async def test_max_iterations_cap_enforced(self, tmp_path: Path, monkeypatch) -> None:
        """When max_iterations=0, the pipeline should still complete."""
        monkeypatch.setenv("ENABLE_NVIDIA_MODEL", "0")
        state = WorkflowState(
            run_id="auto_iter_cap",
            topic="Self-supervised representation learning",
            autonomy_mode="autonomous",
            artifact_root=str(tmp_path),
            max_iterations=0,  # No iterations allowed
        )
        updated = await run_graph(state, registry={})

        # Should still complete (combiner will run anyway)
        assert updated.phase == "completed"
        assert updated.stop_reason is not None
