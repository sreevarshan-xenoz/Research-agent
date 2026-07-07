"""Tests for P39: Research Templates & Presets — template models and registry."""

from __future__ import annotations

import pytest

from research_agent.templates import ResearchTemplate, get_template, list_templates, get_default_template
from research_agent.templates.models import (
    STANDARD,
    LITERATURE_SURVEY,
    META_ANALYSIS,
    SYSTEMATIC_REVIEW,
    CASE_STUDY,
    _BUILTIN_TEMPLATES,
)


class TestTemplateModel:
    """Tests for the ResearchTemplate dataclass."""

    def test_default_template_id(self):
        tmpl = ResearchTemplate(id="test", name="Test")
        assert tmpl.id == "test"
        assert tmpl.name == "Test"

    def test_default_values(self):
        tmpl = ResearchTemplate(id="test", name="Test")
        assert tmpl.icon == "🔬"
        assert tmpl.category == "general"
        assert tmpl.depth_defaults == {"quick": 3, "balanced": 4, "deep": 6}
        assert tmpl.task_sections == [
            "Introduction", "Background", "Methodology",
            "Results", "Discussion", "Conclusion",
        ]
        assert tmpl.preferred_providers == ["arxiv", "semantic_scholar", "openalex", "pubmed", "duckduckgo"]
        assert tmpl.default_latex_template == "ieee-2col"
        assert tmpl.clarification_prompts == []
        assert tmpl.planner_guidance == ""
        assert tmpl.composer_guidance == ""

    def test_to_dict_includes_all_keys(self):
        tmpl = ResearchTemplate(id="test", name="Test", description="A test template")
        d = tmpl.to_dict()
        assert d["id"] == "test"
        assert d["name"] == "Test"
        assert d["description"] == "A test template"
        assert d["icon"] == "🔬"
        assert d["category"] == "general"
        assert "depth_defaults" in d
        assert "task_sections" in d
        assert "section_order" in d
        assert "preferred_providers" in d
        assert "default_latex_template" in d
        assert "intake_instructions" in d
        assert "clarification_prompts" in d

    def test_to_dict_does_not_include_guidance_fields(self):
        """to_dict should NOT include planner_guidance/composer_guidance (internal)."""
        tmpl = ResearchTemplate(id="test", name="Test", planner_guidance="Plan guidance text")
        d = tmpl.to_dict()
        # to_dict only returns public-facing fields
        assert "planner_guidance" not in d
        assert "composer_guidance" not in d

    def test_from_dict_restores_all_fields(self):
        data = {
            "id": "custom_test",
            "name": "Custom Test",
            "description": "A custom template",
            "icon": "🧪",
            "category": "systematic",
            "depth_defaults": {"quick": 2, "balanced": 3, "deep": 5},
            "task_sections": ["Intro", "Methods", "Results"],
            "section_order": ["Intro", "Methods", "Results"],
            "preferred_providers": ["pubmed"],
            "default_latex_template": "acm",
            "intake_instructions": "Do custom research",
            "clarification_prompts": ["What is your question?"],
            "planner_guidance": "Plan with care",
            "composer_guidance": "Compose with style",
        }
        tmpl = ResearchTemplate.from_dict(data)
        assert tmpl.id == "custom_test"
        assert tmpl.name == "Custom Test"
        assert tmpl.icon == "🧪"
        assert tmpl.category == "systematic"
        assert tmpl.depth_defaults == {"quick": 2, "balanced": 3, "deep": 5}
        assert tmpl.task_sections == ["Intro", "Methods", "Results"]
        assert tmpl.preferred_providers == ["pubmed"]
        assert tmpl.default_latex_template == "acm"
        assert tmpl.intake_instructions == "Do custom research"
        assert tmpl.planner_guidance == "Plan with care"
        assert tmpl.composer_guidance == "Compose with style"


class TestBuiltinTemplates:
    """Tests for the 5 built-in template definitions."""

    def test_standard_template_exists(self):
        assert _BUILTIN_TEMPLATES["standard"] is STANDARD
        assert STANDARD.id == "standard"
        assert STANDARD.name == "Standard Research Paper"
        assert STANDARD.category == "general"

    def test_literature_survey_template(self):
        assert _BUILTIN_TEMPLATES["literature_survey"] is LITERATURE_SURVEY
        assert LITERATURE_SURVEY.id == "literature_survey"
        assert LITERATURE_SURVEY.category == "literature_review"
        assert len(LITERATURE_SURVEY.section_order) == 7
        assert LITERATURE_SURVEY.depth_defaults["deep"] == 12
        assert len(LITERATURE_SURVEY.clarification_prompts) >= 3
        assert LITERATURE_SURVEY.default_latex_template == "acm"

    def test_meta_analysis_template(self):
        assert _BUILTIN_TEMPLATES["meta_analysis"] is META_ANALYSIS
        assert META_ANALYSIS.id == "meta_analysis"
        assert META_ANALYSIS.category == "systematic"
        assert len(META_ANALYSIS.section_order) == 10
        assert "pubmed" in META_ANALYSIS.preferred_providers
        assert META_ANALYSIS.intake_instructions != ""
        assert META_ANALYSIS.planner_guidance != ""

    def test_systematic_review_template(self):
        assert _BUILTIN_TEMPLATES["systematic_review"] is SYSTEMATIC_REVIEW
        assert SYSTEMATIC_REVIEW.id == "systematic_review"
        assert SYSTEMATIC_REVIEW.category == "systematic"
        assert "PICO" in SYSTEMATIC_REVIEW.task_sections[1]
        assert len(SYSTEMATIC_REVIEW.clarification_prompts) >= 3
        assert "pubmed" in SYSTEMATIC_REVIEW.preferred_providers

    def test_case_study_template(self):
        assert _BUILTIN_TEMPLATES["case_study"] is CASE_STUDY
        assert CASE_STUDY.id == "case_study"
        assert CASE_STUDY.category == "general"
        assert "Lessons Learned" in CASE_STUDY.section_order
        assert CASE_STUDY.depth_defaults["deep"] == 7
        assert "duckduckgo" in CASE_STUDY.preferred_providers

    def test_all_builtins_have_required_fields(self):
        for tid, tmpl in _BUILTIN_TEMPLATES.items():
            assert tmpl.id, f"Template {tid} missing id"
            assert tmpl.name, f"Template {tid} missing name"
            assert tmpl.description != "", f"Template {tid} missing description"
            assert tmpl.depth_defaults, f"Template {tid} missing depth_defaults"
            assert tmpl.task_sections, f"Template {tid} missing task_sections"
            assert tmpl.preferred_providers, f"Template {tid} missing preferred_providers"
            assert tmpl.planner_guidance != "", f"Template {tid} missing planner_guidance"
            assert tmpl.composer_guidance != "", f"Template {tid} missing composer_guidance"


class TestTemplateRegistry:
    """Tests for the template registry (get/list/add/remove)."""

    def test_get_template_standard(self):
        tmpl = get_template("standard")
        assert tmpl is not None
        assert tmpl.id == "standard"

    def test_get_template_invalid(self):
        tmpl = get_template("nonexistent_template_id")
        assert tmpl is None

    def test_list_templates_contains_builtins(self):
        templates = list_templates()
        ids = {t.id for t in templates}
        assert "standard" in ids
        assert "literature_survey" in ids
        assert "meta_analysis" in ids
        assert "systematic_review" in ids
        assert "case_study" in ids
        assert len(ids) >= 5  # At least 5 built-in

    def test_list_templates_all_have_icons(self):
        for t in list_templates():
            assert t.icon, f"Template {t.id} missing icon"

    def test_get_default_template_is_standard(self):
        default = get_default_template()
        assert default.id == "standard"

    def test_builtins_differ_from_each_other(self):
        """Each built-in template should have unique sections or providers."""
        sections_sets = {t.id: tuple(t.task_sections) for t in list_templates()}
        # Standard and Case Study could share sections, but others are unique
        assert sections_sets["literature_survey"] != sections_sets["meta_analysis"]
        assert sections_sets["systematic_review"] != sections_sets["case_study"]

    def test_preferred_providers_differ(self):
        """Templates should recommend different providers based on domain."""
        lit_survey = get_template("literature_survey")
        meta = get_template("meta_analysis")
        case = get_template("case_study")
        assert lit_survey is not None and meta is not None and case is not None
        # Literature Survey prioritizes semantic_scholar
        assert "semantic_scholar" in lit_survey.preferred_providers
        # Meta-analysis prioritizes pubmed
        assert "pubmed" in meta.preferred_providers
        # Case study uses web search
        assert "duckduckgo" in case.preferred_providers

    def test_template_to_dict_idempotent(self):
        """Converting to dict and back should preserve identity."""
        for t in list_templates():
            d = t.to_dict()
            restored = ResearchTemplate.from_dict({
                **d,
                "planner_guidance": t.planner_guidance,
                "composer_guidance": t.composer_guidance,
            })
            assert restored.id == t.id
            assert restored.name == t.name
            assert restored.task_sections == t.task_sections
            assert restored.depth_defaults == t.depth_defaults


class TestTemplateDepthDefaults:
    """Tests for template-specific depth configurations."""

    def test_standard_depth_defaults(self):
        t = get_template("standard")
        assert t is not None
        assert t.depth_defaults["quick"] == 3
        assert t.depth_defaults["balanced"] == 4
        assert t.depth_defaults["deep"] == 6

    def test_literature_survey_has_higher_counts(self):
        t = get_template("literature_survey")
        assert t is not None
        assert t.depth_defaults["balanced"] >= 5  # Surveys need more tasks

    def test_meta_analysis_has_precise_sections(self):
        t = get_template("meta_analysis")
        assert t is not None
        assert "Statistical Analysis" in t.task_sections
        assert "Heterogeneity Assessment" in t.task_sections
        assert "Publication Bias" in t.task_sections

    def test_systematic_review_has_methodology_sections(self):
        t = get_template("systematic_review")
        assert t is not None
        assert "PICO Framework" in t.task_sections
        assert "Quality Assessment" in t.task_sections
        assert "Evidence Synthesis" in t.task_sections

    def test_case_study_has_practical_focus(self):
        t = get_template("case_study")
        assert t is not None
        assert "Implementation Details" in t.task_sections
        assert "Lessons Learned" in t.task_sections


class TestTemplateOutput:
    """Tests for template output integration."""

    def test_to_dict_round_trip(self):
        """to_dict() should produce valid JSON-serializable output."""
        import json
        for t in list_templates():
            d = t.to_dict()
            # Should be JSON-serializable
            json_str = json.dumps(d, ensure_ascii=False)
            restored = json.loads(json_str)
            assert restored["id"] == t.id
            assert restored["name"] == t.name

    def test_all_templates_have_llm_guidance(self):
        """Every built-in template should have non-empty planner and composer guidance."""
        for t in list_templates():
            assert t.planner_guidance.strip(), f"Template {t.id} missing planner_guidance"
            assert t.composer_guidance.strip(), f"Template {t.id} missing composer_guidance"
