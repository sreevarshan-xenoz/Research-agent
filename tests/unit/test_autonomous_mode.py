"""Unit tests for P26 autonomous mode: intake auto-selection and graph routing.

Tests:
- _is_ambiguous_topic() — topic clarity detection
- _get_candidate_topics() — topic source prioritization
- _auto_select_topic() — auto-select logic (empty, signal, normal)
- intake_node() — full async intake with autonomous mode flows
- _route_after_clarifier() — routing decision in autonomous mode
"""

from __future__ import annotations

from typing import Any

import pytest

from research_agent.orchestration.graph import _route_after_clarifier
from research_agent.orchestration.nodes.intake import (
    _auto_select_topic,
    _get_candidate_topics,
    _is_ambiguous_topic,
    intake_node,
)


# =========================================================================
# _is_ambiguous_topic
# =========================================================================


class TestIsAmbiguousTopic:
    def test_short_topic_is_ambiguous(self) -> None:
        assert _is_ambiguous_topic("AI") is True

    def test_four_words_or_less_is_ambiguous(self) -> None:
        assert _is_ambiguous_topic("machine learning research") is True

    def test_specific_long_topic_not_ambiguous(self) -> None:
        assert _is_ambiguous_topic("Large Language Model Reasoning Capabilities") is False

    def test_broad_marker_makes_ambiguous(self) -> None:
        assert _is_ambiguous_topic("What is the future of AI research technology") is True

    def test_clarification_context_not_ambiguous(self) -> None:
        topic = "Transformers for NLP\n\nClarification context: User specified focus on efficiency"
        assert _is_ambiguous_topic(topic) is False

    def test_empty_string_ambiguous(self) -> None:
        assert _is_ambiguous_topic("") is True

    def test_whitespace_only_ambiguous(self) -> None:
        assert _is_ambiguous_topic("   ") is True


# =========================================================================
# _get_candidate_topics
# =========================================================================


class TestGetCandidateTopics:
    def test_prioritizes_past_research_topics(self) -> None:
        state: dict[str, Any] = {
            "past_research_topics": ["My past topic A", "My past topic B"],
        }
        candidates = _get_candidate_topics(state)
        assert candidates == ["My past topic A", "My past topic B"]

    def test_falls_back_to_fallback_list_when_no_past_topics(self) -> None:
        state: dict[str, Any] = {
            "past_research_topics": [],
        }
        candidates = _get_candidate_topics(state)
        # Should return the hardcoded fallback list
        assert len(candidates) == 8
        assert "Large Language Model Reasoning Capabilities" in candidates

    def test_empty_past_topics_fallsback(self) -> None:
        state: dict[str, Any] = {}
        candidates = _get_candidate_topics(state)
        assert len(candidates) == 8
        assert "Autonomous Agent Architectures" in candidates


# =========================================================================
# _auto_select_topic
# =========================================================================


class TestAutoSelectTopic:
    def test_empty_topic_auto_selects(self) -> None:
        state: dict[str, Any] = {
            "topic": "",
            "past_research_topics": ["Custom past research"],
        }
        result = _auto_select_topic(state)
        assert result == "Custom past research"

    def test_auto_discover_signal_auto_selects(self) -> None:
        state: dict[str, Any] = {
            "topic": "auto-discover",
            "past_research_topics": ["Past topic"],
        }
        result = _auto_select_topic(state)
        assert result == "Past topic"

    def test_auto_signal_variant_auto_selects(self) -> None:
        state: dict[str, Any] = {
            "topic": "auto_discover",
            "past_research_topics": ["Past topic"],
        }
        result = _auto_select_topic(state)
        assert result == "Past topic"

    def test_specific_topic_returns_none(self) -> None:
        state: dict[str, Any] = {
            "topic": "Transformers in NLP",
        }
        result = _auto_select_topic(state)
        assert result is None

    def test_isolates_whitespace_topics(self) -> None:
        state: dict[str, Any] = {
            "topic": "   ",
        }
        result = _auto_select_topic(state)
        assert result is not None  # auto-selected from fallbacks


# =========================================================================
# intake_node — async integration
# =========================================================================


class TestIntakeNode:
    """Tests for the async intake_node with various autonomy modes."""

    _BASE_STATE: dict[str, Any] = {
        "run_id": "test-intake",
        "topic": "",
        "template": "ieee",
        "language": "en",
        "phase": "init",
        "iteration_index": 0,
        "max_iterations": 4,
        "depth": "balanced",
        "autonomy_mode": "hybrid",
        "max_runtime_minutes": 25,
        "max_cost_usd": 5.0,
        "estimated_cost_usd": 0.0,
        "started_at": 0.0,
        "interrupted": False,
        "stop_reason": None,
        "tasks": [],
        "section_confidence": {},
        "clarification_questions": [],
        "needs_clarification": False,
        "task_findings": {},
        "critic_notes": [],
        "critic_user_feedback": None,
        "combined_sections": [],
        "citations": [],
        "figures": [],
        "latex_main": "",
        "bibtex": "",
        "presentation_tex": None,
        "poster_tex": None,
        "future_research_agenda": None,
        "gap_analysis": None,
        "comparison_table": None,
        "guard_report": None,
        "math_verification_report": None,
        "peer_review_report": None,
        "knowledge_graph": None,
        "citation_graph_data": None,
        "bias_report": None,
        "artifact_root": "artifacts",
        "artifact_dir": "",
        "acm_layout": None,
        "run_warnings": [],
        "multi_modal_results": [],
        "peer_reviews": [],
        "peer_review_meta": None,
        "peer_review_personas": [],
        "search_rounds": {},
        "termination_signals": {},
        "chained_papers": [],
        "chained_paper_ids": [],
        "empirical_claims": [],
        "code_verification_items": [],
        "code_reproducibility_report": None,
        "generated_hypotheses": [],
        "research_strategy": None,
        "gap_exploration": None,
        "past_research_topics": [],
    }

    @pytest.mark.asyncio
    async def test_autonomous_mode_empty_topic_selects_from_past(self) -> None:
        """Autonomous mode with empty topic should auto-select from past research."""
        state = dict(self._BASE_STATE)
        state["autonomy_mode"] = "autonomous"
        state["topic"] = ""
        state["past_research_topics"] = ["My past research topic"]

        result = await intake_node(state)

        assert result["topic"] == "My past research topic"
        assert result["needs_clarification"] is False
        assert any("intake:auto_selected_topic:" in w for w in result["run_warnings"])

    @pytest.mark.asyncio
    async def test_autonomous_mode_no_past_selects_from_fallback(self) -> None:
        """Autonomous mode with empty topic and no past history should use fallbacks."""
        state = dict(self._BASE_STATE)
        state["autonomy_mode"] = "autonomous"
        state["topic"] = ""
        state["past_research_topics"] = []

        result = await intake_node(state)

        # Should pick from the 8 fallback trending topics
        assert result["topic"] in [
            "Large Language Model Reasoning Capabilities",
            "Autonomous Agent Architectures",
            "Retrieval-Augmented Generation Optimization",
            "Vision-Language Model Alignment",
            "Efficient Fine-Tuning Methods",
            "AI Safety and Alignment Research",
            "Scientific Discovery with AI",
            "Causal Machine Learning",
        ]
        assert result["needs_clarification"] is False
        assert any("intake:auto_selected_topic:" in w for w in result["run_warnings"])

    @pytest.mark.asyncio
    async def test_hybrid_mode_empty_topic_does_not_auto_select(self) -> None:
        """Hybrid mode with empty topic should NOT auto-select (should need clarification)."""
        state = dict(self._BASE_STATE)
        state["autonomy_mode"] = "hybrid"
        state["topic"] = ""

        result = await intake_node(state)

        assert result["topic"] == ""
        assert result["needs_clarification"] is True  # empty topic is ambiguous
        assert not any("intake:auto_selected_topic:" in w for w in result["run_warnings"])

    @pytest.mark.asyncio
    async def test_autonomous_mode_specific_topic_preserved(self) -> None:
        """Autonomous mode with a specific topic should not auto-select."""
        state = dict(self._BASE_STATE)
        state["autonomy_mode"] = "autonomous"
        state["topic"] = "Transformers for Efficient Code Generation"
        state["past_research_topics"] = ["Some past topic"]

        result = await intake_node(state)

        assert result["topic"] == "Transformers for Efficient Code Generation"
        assert result["needs_clarification"] is False  # specific topic > 4 words, no broad marker
        assert not any("intake:auto_selected_topic:" in w for w in result["run_warnings"])

    @pytest.mark.asyncio
    async def test_autonomous_auto_discover_signal(self) -> None:
        """Autonomous mode with 'auto-discover' signal should auto-select."""
        state = dict(self._BASE_STATE)
        state["autonomy_mode"] = "autonomous"
        state["topic"] = "auto-discover"

        result = await intake_node(state)

        assert result["topic"] in [
            "Large Language Model Reasoning Capabilities",
            "Autonomous Agent Architectures",
            "Retrieval-Augmented Generation Optimization",
            "Vision-Language Model Alignment",
            "Efficient Fine-Tuning Methods",
            "AI Safety and Alignment Research",
            "Scientific Discovery with AI",
            "Causal Machine Learning",
        ]
        assert result["needs_clarification"] is False
        assert any("intake:auto_selected_topic:" in w for w in result["run_warnings"])

    @pytest.mark.asyncio
    async def test_hybrid_mode_specific_topic_normal_flow(self) -> None:
        """Hybrid mode with a specific topic should pass through without auto-selection."""
        state = dict(self._BASE_STATE)
        state["autonomy_mode"] = "hybrid"
        state["topic"] = "Graph Neural Networks for Molecular Properties"

        result = await intake_node(state)

        assert result["topic"] == "Graph Neural Networks for Molecular Properties"
        assert "run_warnings" in result
        assert not any("intake:auto_selected_topic:" in w for w in result["run_warnings"])


# =========================================================================
# _route_after_clarifier — graph routing
# =========================================================================


class TestRouteAfterClarifier:
    def test_autonomous_mode_skips_clarifier(self) -> None:
        """In autonomous mode, route directly to planner regardless of clarification state."""
        state: dict[str, Any] = {
            "autonomy_mode": "autonomous",
            "needs_clarification": True,
            "clarification_questions": ["What area?"],
        }
        assert _route_after_clarifier(state) == "planner"

    def test_hybrid_mode_needs_clarification_awaits_user(self) -> None:
        """In hybrid mode with clarification needed, route to await_user."""
        state: dict[str, Any] = {
            "autonomy_mode": "hybrid",
            "needs_clarification": True,
            "clarification_questions": ["What area?"],
        }
        assert _route_after_clarifier(state) == "await_user"

    def test_hybrid_mode_no_clarification_goes_to_planner(self) -> None:
        """In hybrid mode without clarification needed, route to planner."""
        state: dict[str, Any] = {
            "autonomy_mode": "hybrid",
            "needs_clarification": False,
            "clarification_questions": [],
        }
        assert _route_after_clarifier(state) == "planner"

    def test_guided_mode_clarification_awaits_user(self) -> None:
        """In guided mode with clarification needed, route to await_user."""
        state: dict[str, Any] = {
            "autonomy_mode": "guided",
            "needs_clarification": True,
            "clarification_questions": ["Specify the domain?"],
        }
        assert _route_after_clarifier(state) == "await_user"

    def test_autonomous_mode_no_clarification_goes_to_planner(self) -> None:
        """In autonomous mode without clarification, still routes to planner."""
        state: dict[str, Any] = {
            "autonomy_mode": "autonomous",
            "needs_clarification": False,
            "clarification_questions": [],
        }
        assert _route_after_clarifier(state) == "planner"

    def test_autonomous_mode_with_clarification_but_no_questions(self) -> None:
        """Edge case: autonomous mode flagged for clarification but no questions."""
        state: dict[str, Any] = {
            "autonomy_mode": "autonomous",
            "needs_clarification": True,
            "clarification_questions": [],
        }
        # Should still skip to planner since autonomy_mode is autonomous
        assert _route_after_clarifier(state) == "planner"
