from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResearchTemplate:
    """Defines a research pipeline template — controls intake, planning, provider selection, and output structure.

    Each template encodes domain-specific knowledge about how to approach
    a particular type of research (literature survey, meta-analysis, etc.),
    which providers to prioritize, and how to structure the final output.
    """

    # Identity
    id: str
    name: str
    description: str = ""
    icon: str = "🔬"  # Emoji for frontend display
    category: str = "general"  # general | literature_review | systematic

    # Pipeline configuration
    depth_defaults: dict[str, int] = field(
        default_factory=lambda: {"quick": 3, "balanced": 4, "deep": 6}
    )
    task_sections: list[str] = field(
        default_factory=lambda: [
            "Introduction",
            "Background",
            "Methodology",
            "Results",
            "Discussion",
            "Conclusion",
        ]
    )
    section_order: list[str] = field(default_factory=lambda: [])

    # Intake & clarification guidance
    clarification_prompts: list[str] = field(default_factory=list)
    intake_instructions: str = ""

    # Provider preferences
    preferred_providers: list[str] = field(
        default_factory=lambda: ["arxiv", "semantic_scholar", "openalex", "pubmed", "duckduckgo"]
    )

    # Output configuration
    default_latex_template: str = "ieee-2col"

    # LLM guidance — injected into planner and composer prompts
    planner_guidance: str = ""
    composer_guidance: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "depth_defaults": dict(self.depth_defaults),
            "task_sections": list(self.task_sections),
            "section_order": list(self.section_order),
            "preferred_providers": list(self.preferred_providers),
            "default_latex_template": self.default_latex_template,
            "intake_instructions": self.intake_instructions,
            "clarification_prompts": list(self.clarification_prompts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchTemplate:
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            icon=data.get("icon", "🔬"),
            category=data.get("category", "general"),
            depth_defaults=data.get("depth_defaults", {}),
            task_sections=data.get("task_sections", []),
            section_order=data.get("section_order", []),
            clarification_prompts=data.get("clarification_prompts", []),
            intake_instructions=data.get("intake_instructions", ""),
            preferred_providers=data.get("preferred_providers", []),
            default_latex_template=data.get("default_latex_template", "ieee-2col"),
            planner_guidance=data.get("planner_guidance", ""),
            composer_guidance=data.get("composer_guidance", ""),
        )


# ── Built-in Template Definitions ──────────────────────────────────────────

STANDARD = ResearchTemplate(
    id="standard",
    name="Standard Research Paper",
    description="General-purpose research paper with balanced coverage of background, methodology, results, and discussion.",
    icon="📄",
    category="general",
    intake_instructions=(
        "Conduct a thorough literature review on the given topic, "
        "covering recent advances, key methodologies, empirical findings, "
        "and future research directions."
    ),
    planner_guidance=(
        "Structure the paper with a standard academic format: "
        "Introduction, Background/Literature Review, Methodology, "
        "Results/Findings, Discussion, and Conclusion."
    ),
    composer_guidance=(
        "Write a standard academic research paper with a balanced "
        "treatment of all sections."
    ),
)

LITERATURE_SURVEY = ResearchTemplate(
    id="literature_survey",
    name="Literature Survey",
    description="Broad-coverage survey paper categorizing and comparing existing work. Emphasis on taxonomies and thematic grouping.",
    icon="📚",
    category="literature_review",
    depth_defaults={"quick": 5, "balanced": 8, "deep": 12},
    task_sections=[
        "Introduction",
        "Taxonomy & Categorization",
        "Thematic Analysis",
        "Comparative Evaluation",
        "Research Gaps",
        "Future Directions",
        "Conclusion",
    ],
    section_order=[
        "Introduction",
        "Taxonomy & Categorization",
        "Thematic Analysis",
        "Comparative Evaluation",
        "Research Gaps",
        "Future Directions",
        "Conclusion",
    ],
    clarification_prompts=[
        "What is the scope of literature to cover? (e.g., last 5 years, specific venues)",
        "Which sub-topics or application domains should be included?",
        "Do you have specific comparison criteria in mind? (e.g., accuracy, efficiency, scalability)",
    ],
    intake_instructions=(
        "Conduct a broad-coverage literature survey on the given topic. "
        "Focus on categorizing existing work, identifying thematic groups, "
        "and comparing approaches across key dimensions."
    ),
    preferred_providers=["semantic_scholar", "arxiv", "openalex"],
    default_latex_template="acm",
    planner_guidance=(
        "Design the survey with a strong categorization structure. "
        "Include tasks for: systematic literature search, taxonomy development, "
        "thematic grouping, comparative analysis, and gap identification. "
        "Aim for broad coverage across multiple dimensions."
    ),
    composer_guidance=(
        "Write a literature survey paper. "
        "Focus on categorization and comparison rather than novel methodology. "
        "Structure around thematic groups with clear taxonomies. "
        "Include a comparison table and gap analysis."
    ),
)

META_ANALYSIS = ResearchTemplate(
    id="meta_analysis",
    name="Meta-Analysis",
    description="Quantitative synthesis of results across multiple studies with statistical aggregation and effect size analysis.",
    icon="📊",
    category="systematic",
    depth_defaults={"quick": 4, "balanced": 6, "deep": 10},
    task_sections=[
        "Introduction",
        "Search Strategy",
        "Inclusion Criteria",
        "Data Extraction",
        "Statistical Analysis",
        "Results",
        "Heterogeneity Assessment",
        "Publication Bias",
        "Discussion",
        "Conclusion",
    ],
    section_order=[
        "Introduction",
        "Search Strategy",
        "Inclusion Criteria",
        "Data Extraction",
        "Statistical Analysis",
        "Results",
        "Heterogeneity Assessment",
        "Publication Bias",
        "Discussion",
        "Conclusion",
    ],
    clarification_prompts=[
        "What is the research question or hypothesis being tested?",
        "What are the inclusion/exclusion criteria for studies?",
        "Which effect size metric should be used? (e.g., Cohen's d, odds ratio, correlation)",
        "What is the expected heterogeneity across studies?",
    ],
    preferred_providers=["pubmed", "semantic_scholar", "arxiv"],
    intake_instructions=(
        "Conduct a meta-analysis on the given topic. "
        "Focus on finding studies with quantitative results that can be "
        "statistically aggregated. Extract effect sizes, sample sizes, "
        "and confidence intervals."
    ),
    default_latex_template="ieee-2col",
    planner_guidance=(
        "Design the research for a quantitative meta-analysis. "
        "Include tasks for: systematic literature search with inclusion/exclusion criteria, "
        "data extraction of statistical results, effect size computation, "
        "heterogeneity assessment, publication bias detection, and result synthesis. "
        "Prioritize finding studies with comparable quantitative metrics."
    ),
    composer_guidance=(
        "Write a meta-analysis paper following PRISMA guidelines. "
        "Include a PRISMA flow diagram description, forest plot descriptions, "
        "funnel plot analysis, and statistical synthesis of results. "
        "Focus on quantitative aggregation and methodological rigor."
    ),
)

SYSTEMATIC_REVIEW = ResearchTemplate(
    id="systematic_review",
    name="Systematic Review",
    description="Structured review following PRISMA methodology with PICO framework, quality assessment, and evidence synthesis.",
    icon="🔍",
    category="systematic",
    depth_defaults={"quick": 5, "balanced": 7, "deep": 10},
    task_sections=[
        "Introduction",
        "PICO Framework",
        "Search Strategy",
        "Study Selection",
        "Quality Assessment",
        "Data Extraction",
        "Evidence Synthesis",
        "Discussion",
        "Limitations",
        "Conclusion",
    ],
    section_order=[
        "Introduction",
        "PICO Framework",
        "Search Strategy",
        "Study Selection",
        "Quality Assessment",
        "Data Extraction",
        "Evidence Synthesis",
        "Discussion",
        "Limitations",
        "Conclusion",
    ],
    clarification_prompts=[
        "What is the PICO framework? (Population, Intervention, Comparison, Outcome)",
        "What databases should be searched? (e.g., PubMed, Scopus, Web of Science)",
        "What is the time range for included studies?",
        "Are there specific quality assessment tools to use? (e.g., PRISMA, AMSTAR, Cochrane)",
    ],
    intake_instructions=(
        "Conduct a systematic review following PRISMA guidelines. "
        "Use the PICO framework to structure the research question. "
        "Focus on methodological rigor, study quality assessment, "
        "and structured evidence synthesis."
    ),
    preferred_providers=["pubmed", "semantic_scholar", "openalex"],
    default_latex_template="ieee-2col",
    planner_guidance=(
        "Design the research following systematic review methodology. "
        "Include tasks for: PICO framework definition, multi-database search strategy, "
        "study selection with PRISMA flow, quality assessment using established tools, "
        "structured data extraction, and evidence synthesis. "
        "Prioritize methodological transparency and reproducibility."
    ),
    composer_guidance=(
        "Write a systematic review following PRISMA 2020 guidelines. "
        "Include a PRISMA flow diagram, study characteristics table, "
        "risk of bias assessment, and structured evidence synthesis. "
        "Format as a rigorous, reproducible systematic review."
    ),
)

CASE_STUDY = ResearchTemplate(
    id="case_study",
    name="Case Study",
    description="Deep-dive analysis of a specific implementation, application, or system with detailed methodology and lessons learned.",
    icon="📋",
    category="general",
    depth_defaults={"quick": 3, "balanced": 5, "deep": 7},
    task_sections=[
        "Introduction",
        "Background & Context",
        "System/Application Description",
        "Implementation Details",
        "Evaluation",
        "Lessons Learned",
        "Discussion",
        "Conclusion",
    ],
    section_order=[
        "Introduction",
        "Background & Context",
        "System/Application Description",
        "Implementation Details",
        "Evaluation",
        "Lessons Learned",
        "Discussion",
        "Conclusion",
    ],
    clarification_prompts=[
        "What specific system, application, or implementation is being analyzed?",
        "What is the context or domain of the case study?",
        "What evaluation criteria should be used?",
        "Are there specific lessons learned or best practices to highlight?",
    ],
    intake_instructions=(
        "Conduct a detailed case study analysis of a specific implementation or system. "
        "Focus on practical details, implementation decisions, evaluation results, "
        "and actionable lessons learned."
    ),
    preferred_providers=["duckduckgo", "arxiv", "semantic_scholar"],
    default_latex_template="acm",
    planner_guidance=(
        "Design the research as a detailed case study. "
        "Include tasks for: context and background research, "
        "deep implementation analysis, practical evaluation, "
        "lessons learned extraction, and actionable recommendations. "
        "Focus on providing concrete, detailed findings rather than broad coverage."
    ),
    composer_guidance=(
        "Write a case study paper focusing on practical details. "
        "Structure around the specific implementation or application. "
        "Include detailed descriptions, evaluation metrics, "
        "and actionable lessons learned. Use a narrative but rigorous style."
    ),
)

# Registry of all built-in templates
_BUILTIN_TEMPLATES: dict[str, ResearchTemplate] = {
    "standard": STANDARD,
    "literature_survey": LITERATURE_SURVEY,
    "meta_analysis": META_ANALYSIS,
    "systematic_review": SYSTEMATIC_REVIEW,
    "case_study": CASE_STUDY,
}
