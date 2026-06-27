from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from research_agent.orchestration.survey import (
    SurveyTopic,
    SurveyResult,
    plan_survey_topics,
    identify_cross_cutting_themes,
    run_survey,
)
from research_agent.output.survey_generator import (
    generate_survey_paper,
    generate_taxonomy_table,
    generate_timeline,
    generate_research_landscape,
    _extract_year,
    _count_papers,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def sample_topics() -> list[SurveyTopic]:
    return [
        SurveyTopic(
            name="Transformer Architectures",
            description="Attention-based architectures for sequence modeling",
            task_id="survey_t1",
            key_papers=[
                {"title": "Attention Is All You Need", "year": 2017, "authors": ["Vaswani et al."]},
                {"title": "BERT: Pre-training of Deep Bidirectional Transformers", "year": 2019, "authors": ["Devlin et al."]},
            ],
            summary="Transformers have revolutionized NLP with self-attention mechanisms.",
        ),
        SurveyTopic(
            name="Reinforcement Learning",
            description="Learning through environment interaction",
            task_id="survey_t2",
            key_papers=[
                {"title": "Human-level control through deep reinforcement learning", "year": 2015, "authors": ["Mnih et al."]},
            ],
            summary="RL has achieved superhuman performance in games and robotics.",
        ),
        SurveyTopic(
            name="Computer Vision",
            description="Visual understanding with deep learning",
            task_id="survey_t3",
            key_papers=[
                {"title": "Deep Residual Learning for Image Recognition", "year": 2016, "authors": ["He et al."]},
                {"title": "Generative Adversarial Networks", "year": 2014, "authors": ["Goodfellow et al."]},
                {"title": "An Image is Worth 16x16 Words", "year": 2021, "authors": ["Dosovitskiy et al."]},
            ],
            summary="CNNs and ViTs dominate modern computer vision.",
        ),
    ]


# ──────────────────────────────────────────────
# SurveyTopic tests
# ──────────────────────────────────────────────

class TestSurveyTopic:
    def test_default_fields(self):
        topic = SurveyTopic(name="Test Topic", description="Test description")
        assert topic.name == "Test Topic"
        assert topic.task_id == ""
        assert topic.findings == {}
        assert topic.key_papers == []
        assert topic.summary == ""

    def test_with_task_id(self):
        topic = SurveyTopic(name="Topic", description="Desc", task_id="t1")
        assert topic.task_id == "t1"


# ──────────────────────────────────────────────
# Plan Survey Topics tests
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestPlanSurveyTopics:
    async def test_llm_returns_valid_topics(self):
        mock_result = {
            "topics": [
                {"name": "Transformers", "description": "Attention models"},
                {"name": "CNNs", "description": "Convolutional networks"},
                {"name": "GNNs", "description": "Graph neural networks"},
            ]
        }
        with patch("research_agent.orchestration.survey.agenerate_json", new=AsyncMock(return_value=mock_result)):
            topics = await plan_survey_topics("Deep Learning", num_topics=3)
            assert len(topics) == 3
            assert topics[0].name == "Transformers"
            assert topics[1].name == "CNNs"
            assert topics[2].name == "GNNs"

    async def test_llm_returns_invalid_format(self):
        with patch("research_agent.orchestration.survey.agenerate_json", new=AsyncMock(return_value=None)):
            topics = await plan_survey_topics("Deep Learning", num_topics=3)
            # Should fall back to generated topics
            assert len(topics) == 3
            assert all(t.name for t in topics)

    async def test_llm_returns_empty(self):
        with patch("research_agent.orchestration.survey.agenerate_json", new=AsyncMock(return_value={"topics": []})):
            topics = await plan_survey_topics("Deep Learning", num_topics=5)
            # Should use fallback topics
            assert len(topics) == 5

    async def test_num_topics_respected(self):
        with patch("research_agent.orchestration.survey.agenerate_json", new=AsyncMock(return_value=None)):
            topics = await plan_survey_topics("AI", num_topics=7)
            assert len(topics) == 7


# ──────────────────────────────────────────────
# Identify Cross-Cutting Themes tests
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestIdentifyCrossCuttingThemes:
    async def test_llm_returns_findings(self, sample_topics):
        mock_result = {"findings": ["Transformers are dominant.", "RL excels in games.", "Vision is evolving."]}
        with patch("research_agent.orchestration.survey.agenerate_json", new=AsyncMock(return_value=mock_result)):
            findings = await identify_cross_cutting_themes(sample_topics, "AI")
            assert len(findings) == 3
            assert "Transformers are dominant." in findings

    async def test_llm_returns_invalid_format(self, sample_topics):
        with patch("research_agent.orchestration.survey.agenerate_json", new=AsyncMock(return_value=None)):
            findings = await identify_cross_cutting_themes(sample_topics, "AI")
            # Should fall back
            assert len(findings) >= 3


# ──────────────────────────────────────────────
# Survey Paper Generation tests
# ──────────────────────────────────────────────

class TestGenerateSurveyPaper:
    def test_generates_full_paper(self, sample_topics):
        key_findings = ["Transformers dominate NLP.", "RL achieves superhuman performance."]
        paper = generate_survey_paper(
            broad_topic="Artificial Intelligence",
            topics=sample_topics,
            key_findings=key_findings,
        )

        assert "# A Comprehensive Survey of Artificial Intelligence" in paper
        assert "## Abstract" in paper
        assert "## 1. Introduction" in paper
        assert "## 2. Background and Fundamentals" in paper
        assert "## 3. Taxonomy and Categorization" in paper
        assert "## 4. Comparative Analysis" in paper
        assert "## 5. Key Challenges" in paper
        assert "## 6. Future Research Directions" in paper
        assert "## 7. Conclusion" in paper
        assert "## References" in paper

    def test_references_include_papers(self, sample_topics):
        paper = generate_survey_paper(
            broad_topic="AI",
            topics=sample_topics,
            key_findings=["Finding"],
        )
        # Should include paper titles in references
        assert "Attention Is All You Need" in paper
        assert "Deep Residual Learning" in paper
        assert "Human-level control" in paper

    def test_empty_topics(self):
        paper = generate_survey_paper(
            broad_topic="AI",
            topics=[],
            key_findings=[],
        )
        assert "A Comprehensive Survey of AI" in paper
        assert "## Abstract" in paper

    def test_key_findings_appear_in_abstract(self, sample_topics):
        key_findings = ["This is a key finding"]
        paper = generate_survey_paper(
            broad_topic="AI",
            topics=sample_topics,
            key_findings=key_findings,
        )
        assert "This is a key finding" in paper


# ──────────────────────────────────────────────
# Taxonomy Table tests
# ──────────────────────────────────────────────

class TestGenerateTaxonomyTable:
    def test_generates_table(self, sample_topics):
        table = generate_taxonomy_table(sample_topics)
        assert "## Taxonomy Table" in table
        assert "| Sub-Area |" in table
        assert "Transformer Architectures" in table
        assert "Reinforcement Learning" in table
        assert "Computer Vision" in table

    def test_maturity_levels(self, sample_topics):
        table = generate_taxonomy_table(sample_topics)
        assert "Mature" in table or "Growing" in table or "Emerging" in table

    def test_empty_topics(self):
        table = generate_taxonomy_table([])
        assert "## Taxonomy Table" in table
        assert "| Sub-Area |" in table


# ──────────────────────────────────────────────
# Timeline tests
# ──────────────────────────────────────────────

class TestGenerateTimeline:
    def test_generates_timeline(self, sample_topics):
        timeline = generate_timeline(sample_topics)
        assert "## Research Timeline" in timeline
        # Papers from different years
        assert "2015" in timeline or "2014" in timeline or "2016" in timeline or "2017" in timeline

    def test_papers_sorted_by_year(self, sample_topics):
        timeline = generate_timeline(sample_topics)
        lines = timeline.split("\n")
        years_found = []
        for line in lines:
            if line.startswith("### ") and line[4:].strip().isdigit():
                years_found.append(int(line[4:].strip()))
        assert years_found == sorted(years_found)

    def test_empty_topics(self):
        timeline = generate_timeline([])
        assert "Insufficient data" in timeline


# ──────────────────────────────────────────────
# Research Landscape tests
# ──────────────────────────────────────────────

class TestGenerateResearchLandscape:
    def test_generates_landscape(self, sample_topics):
        landscape = generate_research_landscape(sample_topics)
        assert "## Research Landscape" in landscape
        assert "```mermaid" in landscape
        assert "mindmap" in landscape
        assert "Transformer Architectures" in landscape
        assert "Reinforcement Learning" in landscape
        assert "Computer Vision" in landscape

    def test_empty_topics(self):
        landscape = generate_research_landscape([])
        assert "## Research Landscape" in landscape
        assert "```mermaid" in landscape


# ──────────────────────────────────────────────
# Utility function tests
# ──────────────────────────────────────────────

class TestExtractYear:
    def test_int_year(self):
        assert _extract_year({"year": 2020}) == 2020

    def test_str_year(self):
        assert _extract_year({"year": "2021"}) == 2021

    def test_missing_year(self):
        assert _extract_year({"title": "Paper"}) == 0

    def test_none_year(self):
        assert _extract_year({"year": None}) == 0

    def test_invalid_str_year(self):
        assert _extract_year({"year": "unknown"}) == 0


class TestCountPapers:
    def test_counts_unique_papers(self, sample_topics):
        assert _count_papers(sample_topics) == 6

    def test_duplicate_titles(self):
        topics = [
            SurveyTopic(name="T1", description="D1", key_papers=[
                {"title": "Same Paper", "year": 2020},
            ]),
            SurveyTopic(name="T2", description="D2", key_papers=[
                {"title": "Same Paper", "year": 2020},
                {"title": "Different Paper", "year": 2021},
            ]),
        ]
        assert _count_papers(topics) == 2

    def test_empty_topics(self):
        assert _count_papers([]) == 0


# ──────────────────────────────────────────────
# Run Survey integration test (mocked)
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestRunSurvey:
    async def test_full_survey_pipeline(self):
        """Test the full survey pipeline with mocked LLM and search."""
        mock_plan_result = {
            "topics": [
                {"name": "Transformers", "description": "Attention models"},
                {"name": "CNNs", "description": "Convolutional networks"},
            ]
        }
        mock_findings_result = {"findings": ["Finding one", "Finding two"]}
        mock_search_result = {
            "arxiv": MagicMock(items=[
                {"title": "Paper 1", "year": 2020, "authors": ["Author A"]},
            ], warnings=[]),
        }
        mock_registry = {
            "arxiv": MagicMock(
                provider_name="arxiv",
                is_searcher=True,
                search=MagicMock(return_value=mock_search_result["arxiv"]),
                asearch=AsyncMock(return_value=mock_search_result["arxiv"]),
            ),
        }

        with (
            patch("research_agent.orchestration.survey.agenerate_json", side_effect=[mock_plan_result, mock_findings_result]),
            patch("research_agent.orchestration.survey.agenerate_text", new=AsyncMock(return_value="Generated summary.")),
            patch("research_agent.orchestration.survey.arun_multi_source_search", new=AsyncMock(return_value=mock_search_result)),
        ):
            result = await run_survey(
                broad_topic="Deep Learning",
                registry=mock_registry,
                num_topics=2,
            )

            assert isinstance(result, SurveyResult)
            assert result.topic == "Deep Learning"
            assert len(result.sub_topics) == 2
            assert len(result.key_findings) >= 2
            assert result.survey_markdown
            assert "A Comprehensive Survey of Deep Learning" in result.survey_markdown
            assert result.taxonomy_table
            assert result.timeline
            assert result.research_landscape
            assert result.run_id.startswith("survey-")
            assert result.duration_seconds >= 0


    async def test_pipeline_with_fallback(self):
        """Test pipeline handles LLM failures gracefully."""
        mock_registry = {
            "arxiv": MagicMock(
                provider_name="arxiv",
                is_searcher=True,
                search=MagicMock(return_value=MagicMock(items=[], warnings=["API error"])),
                asearch=AsyncMock(return_value=MagicMock(items=[], warnings=["API error"])),
            ),
        }

        with (
            patch("research_agent.orchestration.survey.agenerate_json", return_value=None),
            patch("research_agent.orchestration.survey.agenerate_text", return_value="Fallback summary."),
            patch("research_agent.orchestration.survey.arun_multi_source_search",
                  new=AsyncMock(return_value={"arxiv": MagicMock(items=[], warnings=[])})),
        ):
            result = await run_survey(
                broad_topic="Computer Science",
                registry=mock_registry,
                num_topics=3,
            )

            assert isinstance(result, SurveyResult)
            assert result.topic == "Computer Science"
            # Should have fallback topics
            assert len(result.sub_topics) == 3
            assert result.survey_markdown
            # Should contain fallback content
            assert "A Comprehensive Survey of Computer Science" in result.survey_markdown
