"""P39: Template Library — storage, CRUD, and preset management.

Provides the storage layer for research templates and conference presets,
bridging the API routes (template_routes.py) to the template data models
(templates/registry.py).

Templates define the research pipeline configuration (sections, depth,
providers, LLM guidance), while presets define output formatting settings
(LateX template, columns, venue).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from research_agent.templates import ResearchTemplate, get_template as _get_builtin

logger = logging.getLogger(__name__)

# Module-level override for the store path (set by set_template_store_path for tests)
_store_path_override: str | None = None


def _resolve_store_path() -> str:
    if _store_path_override is not None:
        return _store_path_override
    try:
        from research_agent.config import load_settings
        settings = load_settings()
        return settings.template_library.store_path
    except Exception:
        return ".runtime/templates.json"


# ── Template CRUD ──────────────────────────────────────────────────────────

def list_templates() -> list[dict[str, Any]]:
    """List all available templates (built-in + custom) as dicts."""
    from research_agent.templates import list_templates as _list_all
    return [t.to_dict() for t in _list_all()]


def get_template(template_id: str) -> dict[str, Any] | None:
    """Get a single template by ID, or None if not found."""
    t = _get_builtin(template_id)
    if t is None:
        return None
    return t.to_dict()


def create_template(data: dict[str, Any]) -> dict[str, Any]:
    """Create a custom template from a dict. Raises if ID already exists."""
    template_id = data.get("template_id", data.get("id", ""))
    if not template_id:
        raise ValueError("template_id is required")

    existing = get_template(template_id)
    if existing:
        raise ValueError(f"Template '{template_id}' already exists")

    # Build the template object
    from research_agent.templates.models import ResearchTemplate

    tmpl = ResearchTemplate(
        id=template_id,
        name=data.get("name", template_id),
        description=data.get("description", ""),
        icon=data.get("icon", "📄"),
        category=data.get("category", "general"),
        depth_defaults=data.get("depth_defaults", {"quick": 3, "balanced": 4, "deep": 6}),
        task_sections=data.get("sections", data.get("task_sections", [])),
        clarification_prompts=data.get("clarification_prompts", []),
        intake_instructions=data.get("intake_instructions", ""),
        preferred_providers=data.get("recommended_paper_providers", data.get("preferred_providers", [])),
        default_latex_template=data.get("default_latex_template", "ieee-2col"),
        planner_guidance=data.get("planner_guidance", ""),
        composer_guidance=data.get("composer_guidance", ""),
    )

    # Persist to disk using resolved store path
    from research_agent.templates.registry import add_custom_template
    add_custom_template(tmpl, store_path=Path(_resolve_store_path()))
    return tmpl.to_dict()


def update_template(template_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update a custom template. Returns None if template is built-in or not found."""
    # Check if it's a built-in (cannot modify)
    builtin_ids = {"standard", "literature_survey", "lit_survey", "meta_analysis",
                    "systematic_review", "case_study", "technical_report"}
    if template_id in builtin_ids:
        return None

    from research_agent.templates.registry import _load_custom_templates_from_path
    store_path = Path(_resolve_store_path())
    custom = _load_custom_templates_from_path(store_path)

    if template_id not in custom:
        return None

    tmpl = custom[template_id]
    # Apply updates
    for key, value in updates.items():
        if hasattr(tmpl, key) and value is not None:
            setattr(tmpl, key, value)

    # Persist
    from research_agent.templates.registry import add_custom_template
    add_custom_template(tmpl, store_path=store_path)
    return tmpl.to_dict()


def delete_template(template_id: str) -> bool:
    """Delete a custom template. Built-in templates cannot be deleted."""
    from research_agent.templates.registry import remove_custom_template
    return remove_custom_template(template_id)


# ── Conference Presets ─────────────────────────────────────────────────────

# Built-in conference presets
_BUILTIN_PRESETS: dict[str, dict[str, Any]] = {
    "cvpr": {
        "preset_id": "cvpr",
        "name": "CVPR",
        "venue": "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
        "venue_type": "conference",
        "latex_template": "ieee-2col",
        "columns": 2,
        "max_pages": 8,
        "paper_providers_mode": "computer_vision",
        "description": "Computer Vision and Pattern Recognition conference format. 8-page limit, double-blind review.",
        "icon": "🖼️",
        "recommended_depth": "balanced",
        "tags": ["computer vision", "pattern recognition", "deep learning", "CV"],
    },
    "neurips": {
        "preset_id": "neurips",
        "name": "NeurIPS",
        "venue": "Neural Information Processing Systems",
        "venue_type": "conference",
        "latex_template": "ieee-2col",
        "columns": 2,
        "max_pages": 9,
        "paper_providers_mode": "ml_neural",
        "description": "Neural Information Processing Systems conference format. 9-page main content + unlimited references/appendix.",
        "icon": "🧠",
        "recommended_depth": "deep",
        "tags": ["machine learning", "neural networks", "AI", "NeurIPS"],
    },
    "icml": {
        "preset_id": "icml",
        "name": "ICML",
        "venue": "International Conference on Machine Learning",
        "venue_type": "conference",
        "latex_template": "acm",
        "columns": 2,
        "max_pages": 8,
        "paper_providers_mode": "ml_neural",
        "description": "International Conference on Machine Learning format. 8-page limit with broad ML coverage.",
        "icon": "🤖",
        "recommended_depth": "balanced",
        "tags": ["machine learning", "optimization", "statistics", "ICML"],
    },
    "acl": {
        "preset_id": "acl",
        "name": "ACL",
        "venue": "Association for Computational Linguistics",
        "venue_type": "conference",
        "latex_template": "acm",
        "columns": 2,
        "max_pages": 8,
        "paper_providers_mode": "nlp",
        "description": "Association for Computational Linguistics conference format. 8-page limit, ACL style guidelines.",
        "icon": "💬",
        "recommended_depth": "balanced",
        "tags": ["NLP", "computational linguistics", "language models", "ACL"],
    },
}

_custom_presets: dict[str, dict[str, Any]] | None = None


def _load_custom_presets() -> dict[str, dict[str, Any]]:
    global _custom_presets
    if _custom_presets is not None:
        return _custom_presets
    store_path = Path(_resolve_store_path())

    _custom_presets = _load_presets_from_path(store_path)
    return _custom_presets


def _load_presets_from_path(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        presets_data = data.get("presets", {}) if isinstance(data, dict) else {}
        return presets_data if isinstance(presets_data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_custom_presets(presets: dict[str, dict[str, Any]]) -> None:
    global _custom_presets
    store_path = Path(_resolve_store_path())

    store_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data to preserve templates
    existing = {}
    if store_path.exists():
        try:
            existing = json.loads(store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    existing["presets"] = presets
    store_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    _custom_presets = presets


def list_presets() -> list[dict[str, Any]]:
    """List all available presets (built-in + custom)."""
    presets = list(_BUILTIN_PRESETS.values())
    presets.extend(_load_custom_presets().values())
    return presets


def get_preset(preset_id: str) -> dict[str, Any] | None:
    """Get a single preset by ID."""
    if preset_id in _BUILTIN_PRESETS:
        return _BUILTIN_PRESETS[preset_id]
    return _load_custom_presets().get(preset_id)


def create_preset(data: dict[str, Any]) -> dict[str, Any]:
    """Create a custom preset."""
    preset_id = data.get("preset_id", "")
    if not preset_id:
        raise ValueError("preset_id is required")

    custom = _load_custom_presets()
    custom[preset_id] = {
        "preset_id": preset_id,
        "name": data.get("name", preset_id),
        "venue": data.get("venue", ""),
        "venue_type": data.get("venue_type", "conference"),
        "latex_template": data.get("latex_template", "ieee-2col"),
        "columns": data.get("columns", 2),
        "max_pages": data.get("max_pages"),
        "paper_providers_mode": data.get("paper_providers_mode", "standard"),
        "description": data.get("description", ""),
        "icon": data.get("icon", "🎯"),
        "recommended_depth": data.get("recommended_depth", "balanced"),
        "tags": data.get("tags", []),
    }
    _save_custom_presets(custom)
    return custom[preset_id]


def delete_preset(preset_id: str) -> bool:
    """Delete a custom preset. Built-in presets cannot be deleted."""
    if preset_id in _BUILTIN_PRESETS:
        return False

    custom = _load_custom_presets()
    if preset_id not in custom:
        return False

    del custom[preset_id]
    _save_custom_presets(custom)
    return True


# ── Template Application ───────────────────────────────────────────────────

def apply_template_to_state(
    template_id: str,
    state_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate state configuration overrides from a template.

    Returns a dict that can be merged into a WorkflowState to configure
    the research pipeline according to the template's specifications.
    """
    t = _get_builtin(template_id)
    if t is None:
        raise ValueError(f"Template '{template_id}' not found")

    config: dict[str, Any] = {
        "research_template": t.id,
        "depth_defaults": dict(t.depth_defaults),
        "task_sections": list(t.task_sections),
        "section_order": list(t.section_order) if t.section_order else list(t.task_sections),
        "preferred_providers": list(t.preferred_providers),
        "default_latex_template": t.default_latex_template,
    }

    if state_overrides:
        config.update(state_overrides)

    return config


def apply_preset_to_state(
    preset_id: str,
    state_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate state configuration overrides from a preset.

    Presets primarily affect output formatting (LaTeX template, columns).
    """
    prs = get_preset(preset_id)
    if prs is None:
        raise ValueError(f"Preset '{preset_id}' not found")

    config: dict[str, Any] = {
        "template": prs.get("latex_template", "ieee-2col"),
        "columns": prs.get("columns", 2),
        "depth": prs.get("recommended_depth", "balanced"),
    }

    if state_overrides:
        config.update(state_overrides)

    return config


def set_template_store_path(path: str | Path) -> None:
    """Override the default template storage path.

    Useful for tests and multi-user setups where each user has
    their own template library. This sets a module-level override
    that persists until the next call to set_template_store_path.
    """
    global _custom_templates, _custom_presets, _store_path_override
    _custom_templates = None
    _custom_presets = None
    _store_path_override = str(path)


def get_merged_template_config(
    template_id: str = "standard",
    preset_id: str | None = None,
    manual_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge template + optional preset + manual overrides into a single config.

    Priority: manual_overrides > preset > template > defaults.
    """
    config = apply_template_to_state(template_id)

    if preset_id:
        preset_config = apply_preset_to_state(preset_id)
        # Merge preset into config (preset values override template)
        for key, value in preset_config.items():
            config[key] = value

    if manual_overrides:
        for key, value in manual_overrides.items():
            config[key] = value

    return config
