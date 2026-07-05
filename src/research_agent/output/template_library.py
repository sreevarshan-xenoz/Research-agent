from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import json


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class ResearchTemplate:
    """A reusable research template that controls pipeline behavior.

    Each template defines:
    - Which sections to generate
    - Search strategy (depth, paper count, providers)
    - Analysis type (survey, meta-analysis, review, case study)
    - Default output format (LaTeX template, columns)
    """

    template_id: str
    name: str
    description: str
    category: str  # "literature_survey", "meta_analysis", "systematic_review", "case_study"
    icon: str = "📄"

    # Pipeline settings
    default_depth: str = "balanced"  # quick, balanced, deep
    default_max_iterations: int = 4
    default_max_papers_per_section: int = 15
    default_autonomy: str = "hybrid"  # guided, hybrid, autonomous

    # Output settings
    default_latex_template: str = "ieee-2col"
    default_columns: int = 2
    default_language: str = "en"

    # Sections to generate (ordered)
    sections: list[str] = field(default_factory=lambda: [
        "Introduction",
        "Background and Related Work",
        "Methodology",
        "Results and Analysis",
        "Discussion",
        "Conclusion and Future Work",
    ])

    # Search configuration
    recommended_paper_providers: list[str] = field(
        default_factory=lambda: ["arxiv", "semantic_scholar", "openalex", "pubmed"]
    )
    enable_citation_chaining: bool = True
    enable_deep_research: bool = True
    enable_gap_analysis: bool = True
    enable_comparison_table: bool = True

    # Venue metadata (for conference presets)
    venue: str | None = None
    venue_type: str | None = None  # "conference", "journal"

    # Custom metadata
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "icon": self.icon,
            "default_depth": self.default_depth,
            "default_max_iterations": self.default_max_iterations,
            "default_max_papers_per_section": self.default_max_papers_per_section,
            "default_autonomy": self.default_autonomy,
            "default_latex_template": self.default_latex_template,
            "default_columns": self.default_columns,
            "default_language": self.default_language,
            "sections": self.sections,
            "recommended_paper_providers": self.recommended_paper_providers,
            "enable_citation_chaining": self.enable_citation_chaining,
            "enable_deep_research": self.enable_deep_research,
            "enable_gap_analysis": self.enable_gap_analysis,
            "enable_comparison_table": self.enable_comparison_table,
            "venue": self.venue,
            "venue_type": self.venue_type,
            "tags": self.tags,
        }


@dataclass
class ConferencePreset:
    """A formatting preset for a specific conference/venue."""

    preset_id: str
    name: str
    venue: str
    venue_type: str  # "conference", "journal"
    latex_template: str
    columns: int
    paper_providers_mode: str = "standard"  # standard, full, minimal
    description: str = ""
    icon: str = "🎯"
    recommended_depth: str = "balanced"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "name": self.name,
            "venue": self.venue,
            "venue_type": self.venue_type,
            "latex_template": self.latex_template,
            "columns": self.columns,
            "paper_providers_mode": self.paper_providers_mode,
            "description": self.description,
            "icon": self.icon,
            "recommended_depth": self.recommended_depth,
            "tags": self.tags,
        }


# ---------------------------------------------------------------------------
# Built-in Research Templates
# ---------------------------------------------------------------------------

BUILTIN_TEMPLATES: dict[str, ResearchTemplate] = {
    "standard": ResearchTemplate(
        template_id="standard",
        name="Standard Research Paper",
        description="A comprehensive research paper with full pipeline: introduction, background, methodology, results, discussion, and conclusion. Best for general research topics.",
        category="literature_survey",
        icon="📄",
        default_depth="balanced",
        default_max_iterations=4,
        sections=[
            "Introduction",
            "Background and Related Work",
            "Methodology",
            "Results and Analysis",
            "Discussion",
            "Conclusion and Future Work",
        ],
        tags=["standard", "general"],
    ),
    "lit_survey": ResearchTemplate(
        template_id="lit_survey",
        name="Literature Survey",
        description="A broad literature survey that decomposes a research area into sub-topics and synthesizes findings across them. Generates a survey paper, taxonomy table, timeline, and research landscape.",
        category="literature_survey",
        icon="📚",
        default_depth="deep",
        default_max_iterations=5,
        default_max_papers_per_section=25,
        sections=[
            "Introduction and Scope",
            "Background and Fundamentals",
            "Taxonomy and Categorization",
            "Comparative Analysis of Approaches",
            "Key Challenges and Open Problems",
            "Future Research Directions",
            "Conclusion",
        ],
        enable_gap_analysis=True,
        enable_comparison_table=True,
        tags=["survey", "comprehensive", "taxonomy"],
    ),
    "meta_analysis": ResearchTemplate(
        template_id="meta_analysis",
        name="Meta-Analysis",
        description="A quantitative meta-analysis template focused on statistical aggregation of findings across studies. Emphasizes effect sizes, heterogeneity analysis, and publication bias assessment.",
        category="meta_analysis",
        icon="📊",
        default_depth="deep",
        default_max_iterations=4,
        sections=[
            "Introduction and Rationale",
            "Search Strategy and Inclusion Criteria",
            "Study Selection and Data Extraction",
            "Statistical Analysis and Effect Sizes",
            "Heterogeneity and Subgroup Analysis",
            "Publication Bias Assessment",
            "Discussion and Implications",
            "Conclusion",
        ],
        enable_comparison_table=True,
        enable_gap_analysis=True,
        tags=["meta-analysis", "quantitative", "statistics"],
    ),
    "systematic_review": ResearchTemplate(
        template_id="systematic_review",
        name="Systematic Review",
        description="A PRISMA-guided systematic review with explicit search strategy, inclusion/exclusion criteria, quality assessment, and evidence synthesis. Suitable for evidence-based research.",
        category="systematic_review",
        icon="🔍",
        default_depth="deep",
        default_max_iterations=5,
        default_max_papers_per_section=30,
        sections=[
            "Introduction and Objectives",
            "Methods: Search Strategy",
            "Methods: Inclusion and Exclusion Criteria",
            "Methods: Quality Assessment",
            "Results: Study Selection (PRISMA)",
            "Results: Study Characteristics",
            "Results: Synthesis of Findings",
            "Discussion: Summary of Evidence",
            "Discussion: Limitations",
            "Conclusion",
        ],
        enable_citation_chaining=True,
        enable_deep_research=True,
        enable_comparison_table=True,
        tags=["systematic-review", "prisma", "evidence-based"],
    ),
    "case_study": ResearchTemplate(
        template_id="case_study",
        name="Case Study",
        description="An in-depth case study examining a specific method, application, or phenomenon. Includes detailed background, methodology, implementation, results, and lessons learned.",
        category="case_study",
        icon="📋",
        default_depth="balanced",
        default_max_iterations=3,
        sections=[
            "Introduction and Context",
            "Background and Related Work",
            "Case Description and Setup",
            "Methodology and Implementation",
            "Results and Observations",
            "Lessons Learned and Best Practices",
            "Conclusion and Future Work",
        ],
        enable_deep_research=False,
        enable_gap_analysis=False,
        enable_comparison_table=False,
        tags=["case-study", "practical", "implementation"],
    ),
    "technical_report": ResearchTemplate(
        template_id="technical_report",
        name="Technical Report",
        description="A concise technical report focused on system design, implementation details, and experimental evaluation. Ideal for engineering-focused research with a practical emphasis.",
        category="case_study",
        icon="⚙️",
        default_depth="quick",
        default_max_iterations=2,
        default_max_papers_per_section=10,
        sections=[
            "Introduction",
            "System Architecture and Design",
            "Implementation Details",
            "Experimental Setup",
            "Results and Evaluation",
            "Discussion and Limitations",
            "Conclusion",
        ],
        enable_citation_chaining=False,
        enable_deep_research=False,
        enable_gap_analysis=False,
        enable_comparison_table=True,
        tags=["technical", "report", "engineering"],
    ),
}


# ---------------------------------------------------------------------------
# Built-in Conference Presets
# ---------------------------------------------------------------------------

BUILTIN_PRESETS: dict[str, ConferencePreset] = {
    "cvpr": ConferencePreset(
        preset_id="cvpr",
        name="CVPR",
        venue="IEEE/CVF Conference on Computer Vision and Pattern Recognition",
        venue_type="conference",
        latex_template="ieee-2col",
        columns=2,
        description="Computer Vision and Pattern Recognition — double-blind review, 8-page limit, IEEE format.",
        icon="👁️",
        tags=["cv", "computer-vision", "pattern-recognition"],
    ),
    "neurips": ConferencePreset(
        preset_id="neurips",
        name="NeurIPS",
        venue="Conference on Neural Information Processing Systems",
        venue_type="conference",
        latex_template="ieee-2col",
        columns=2,
        description="Neural Information Processing Systems — prestigious ML conference, 8-page main content + unlimited bibliography/appendix.",
        icon="🧠",
        tags=["ml", "neural-networks", "deep-learning"],
    ),
    "icml": ConferencePreset(
        preset_id="icml",
        name="ICML",
        venue="International Conference on Machine Learning",
        venue_type="conference",
        latex_template="ieee-2col",
        columns=2,
        description="International Conference on Machine Learning — broad ML audience, 8-page limit, flexible format.",
        icon="🤖",
        tags=["ml", "machine-learning"],
    ),
    "acl": ConferencePreset(
        preset_id="acl",
        name="ACL",
        venue="Annual Meeting of the Association for Computational Linguistics",
        venue_type="conference",
        latex_template="acm",
        columns=2,
        description="Association for Computational Linguistics — NLP and computational linguistics, 8-page limit, ACM-format optional.",
        icon="💬",
        tags=["nlp", "computational-linguistics"],
    ),
    "iclr": ConferencePreset(
        preset_id="iclr",
        name="ICLR",
        venue="International Conference on Learning Representations",
        venue_type="conference",
        latex_template="ieee-2col",
        columns=2,
        description="International Conference on Learning Representations — representation learning focus, 8-page limit, open review process.",
        icon="📐",
        tags=["ml", "representations", "deep-learning"],
    ),
    "aaai": ConferencePreset(
        preset_id="aaai",
        name="AAAI",
        venue="AAAI Conference on Artificial Intelligence",
        venue_type="conference",
        latex_template="ieee-2col",
        columns=2,
        description="AAAI Conference on Artificial Intelligence — broad AI, 7-page main content + 2-page references.",
        icon="🌟",
        tags=["ai", "artificial-intelligence"],
    ),
    "sigmod": ConferencePreset(
        preset_id="sigmod",
        name="SIGMOD",
        venue="ACM SIGMOD International Conference on Management of Data",
        venue_type="conference",
        latex_template="acm",
        columns=2,
        description="ACM SIGMOD — data management and databases, 12-page limit, ACM format.",
        icon="🗄️",
        tags=["databases", "data-management"],
    ),
    "nature": ConferencePreset(
        preset_id="nature",
        name="Nature",
        venue="Nature (Journal)",
        venue_type="journal",
        latex_template="ieee-1col",
        columns=1,
        description="Nature journal — broad scientific audience, single-column format, ~4,000 word limit, structured abstract.",
        icon="🔬",
        recommended_depth="deep",
        tags=["science", "general", "journal"],
    ),
    "science": ConferencePreset(
        preset_id="science",
        name="Science",
        venue="Science (Journal)",
        venue_type="journal",
        latex_template="ieee-1col",
        columns=1,
        description="Science journal — broad scientific audience, single-column, ~4,500 word limit, concise format.",
        icon="🧪",
        recommended_depth="deep",
        tags=["science", "general", "journal"],
    ),
    "springer": ConferencePreset(
        preset_id="springer",
        name="Springer LNCS",
        venue="Springer Lecture Notes in Computer Science",
        venue_type="conference",
        latex_template="springer",
        columns=2,
        description="Springer LNCS format — widely used across computer science conferences, flexible page limit.",
        icon="📘",
        tags=["cs", "conference", "springer"],
    ),
}


# ---------------------------------------------------------------------------
# Template Storage & Management
# ---------------------------------------------------------------------------

_custom_templates: dict[str, ResearchTemplate] = {}
_custom_presets: dict[str, ConferencePreset] = {}
_template_store_path: Path | None = None


def _get_store_path() -> Path:
    global _template_store_path
    if _template_store_path is None:
        _template_store_path = Path(".runtime/templates.json")
    return _template_store_path


def set_template_store_path(path: str | Path) -> None:
    global _template_store_path
    _template_store_path = Path(path)


def _load_custom_from_disk() -> None:
    """Load custom templates/presets from the JSON store file."""
    global _custom_templates, _custom_presets
    path = _get_store_path()
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _custom_templates = {
            tid: ResearchTemplate(**tpl)
            for tid, tpl in data.get("templates", {}).items()
        }
        _custom_presets = {
            pid: ConferencePreset(**prs)
            for pid, prs in data.get("presets", {}).items()
        }
    except Exception:
        pass


def _save_custom_to_disk() -> None:
    """Persist custom templates/presets to the JSON store file."""
    path = _get_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "templates": {tid: tpl.to_dict() for tid, tpl in _custom_templates.items()},
        "presets": {pid: prs.to_dict() for pid, prs in _custom_presets.items()},
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_templates() -> list[dict[str, Any]]:
    """Return all available templates (built-in + custom)."""
    _load_custom_from_disk()
    all_templates = {**BUILTIN_TEMPLATES, **_custom_templates}
    return [tpl.to_dict() for tpl in all_templates.values()]


def get_template(template_id: str) -> dict[str, Any] | None:
    """Get a single template by ID."""
    _load_custom_from_disk()
    tpl = BUILTIN_TEMPLATES.get(template_id) or _custom_templates.get(template_id)
    return tpl.to_dict() if tpl else None


def create_template(template: dict[str, Any]) -> dict[str, Any]:
    """Create a new custom template."""
    _load_custom_from_disk()
    tpl = ResearchTemplate(**template)
    _custom_templates[tpl.template_id] = tpl
    _save_custom_to_disk()
    return tpl.to_dict()


def update_template(template_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing custom template."""
    _load_custom_from_disk()
    if template_id not in _custom_templates:
        return None
    existing = _custom_templates[template_id]
    for key, value in updates.items():
        if hasattr(existing, key) and key != "template_id":
            setattr(existing, key, value)
    _custom_templates[template_id] = existing
    _save_custom_to_disk()
    return existing.to_dict()


def delete_template(template_id: str) -> bool:
    """Delete a custom template."""
    _load_custom_from_disk()
    if template_id in _custom_templates:
        del _custom_templates[template_id]
        _save_custom_to_disk()
        return True
    return False


def list_presets() -> list[dict[str, Any]]:
    """Return all available conference presets (built-in + custom)."""
    _load_custom_from_disk()
    all_presets = {**BUILTIN_PRESETS, **_custom_presets}
    return [prs.to_dict() for prs in all_presets.values()]


def get_preset(preset_id: str) -> dict[str, Any] | None:
    """Get a single preset by ID."""
    _load_custom_from_disk()
    prs = BUILTIN_PRESETS.get(preset_id) or _custom_presets.get(preset_id)
    return prs.to_dict() if prs else None


def create_preset(preset: dict[str, Any]) -> dict[str, Any]:
    """Create a new custom preset."""
    _load_custom_from_disk()
    prs = ConferencePreset(**preset)
    _custom_presets[prs.preset_id] = prs
    _save_custom_to_disk()
    return prs.to_dict()


def delete_preset(preset_id: str) -> bool:
    """Delete a custom preset."""
    _load_custom_from_disk()
    if preset_id in _custom_presets:
        del _custom_presets[preset_id]
        _save_custom_to_disk()
        return True
    return False


def apply_template_to_state(
    template_id: str,
    state_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a template to generate state overrides for a WorkflowState.

    Returns a dict of WorkflowState field overrides that should be applied
    when initializing a new run.

    Args:
        template_id: The template ID to apply.
        state_overrides: Optional additional overrides to layer on top.

    Returns:
        Dict of state field values to apply.
    """
    tpl = get_template(template_id)
    if tpl is None:
        # Fall back to standard template
        tpl = get_template("standard") or {}

    overrides: dict[str, Any] = {
        "depth": tpl.get("default_depth", "balanced"),
        "max_iterations": tpl.get("default_max_iterations", 4),
        "template": tpl.get("default_latex_template", "ieee-2col"),
        "language": tpl.get("default_language", "en"),
        "autonomy_mode": tpl.get("default_autonomy", "hybrid"),
    }

    # Sections are used internally by the pipeline
    sections = tpl.get("sections", [])
    if sections:
        overrides["_template_sections"] = sections

    if state_overrides:
        overrides.update(state_overrides)

    return overrides


def apply_preset_to_state(
    preset_id: str,
    state_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a conference preset to generate state overrides.

    Returns a dict of WorkflowState field overrides that configure
    the output format for a specific venue.

    Args:
        preset_id: The preset ID to apply.
        state_overrides: Optional additional overrides to layer on top.

    Returns:
        Dict of state field values to apply.
    """
    prs = get_preset(preset_id)
    if prs is None:
        return {}

    overrides: dict[str, Any] = {
        "template": prs.get("latex_template", "ieee-2col"),
        "depth": prs.get("recommended_depth", "balanced"),
    }

    if state_overrides:
        overrides.update(state_overrides)

    return overrides


def get_merged_template_config(
    template_id: str | None,
    preset_id: str | None,
    manual_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge template, preset, and manual overrides into a single config dict.

    Priority (highest wins): manual_overrides > preset > template > defaults

    Args:
        template_id: Research template ID (optional).
        preset_id: Conference preset ID (optional).
        manual_overrides: Direct user overrides (highest priority).

    Returns:
        Merged configuration dict.
    """
    from research_agent.config import load_settings
    settings = load_settings()

    # Start with defaults
    config: dict[str, Any] = {
        "depth": settings.runtime.mode if hasattr(settings.runtime, "mode") else "balanced",
        "max_iterations": settings.runtime.max_iterations,
        "template": settings.output.default_template,
        "language": settings.output.language,
    }

    # Apply template
    if template_id:
        tpl_overrides = apply_template_to_state(template_id)
        config.update(tpl_overrides)

    # Apply preset (overrides template for output-format fields)
    if preset_id:
        prs_overrides = apply_preset_to_state(preset_id)
        config.update(prs_overrides)

    # Manual overrides have highest priority
    if manual_overrides:
        config.update(manual_overrides)

    return config
