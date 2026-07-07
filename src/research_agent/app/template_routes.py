"""
P39: Research Templates & Presets — API Routes

API endpoints for:
- Browsing the template library (built-in + custom)
- Creating/updating/deleting custom templates
- Browsing conference presets
- Creating/updating/deleting custom presets
- Applying templates/presets to generate state overrides
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

from research_agent.app.auth import User, current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/templates", tags=["templates"])


# ── Request Models ───────────────────────────────────────────

class TemplateCreateRequest(BaseModel):
    template_id: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    category: str = "literature_survey"
    icon: str = "📄"
    default_depth: str = "balanced"
    default_max_iterations: int = 4
    default_max_papers_per_section: int = 15
    default_autonomy: str = "hybrid"
    default_latex_template: str = "ieee-2col"
    default_columns: int = 2
    default_language: str = "en"
    sections: list[str] = Field(default_factory=lambda: [
        "Introduction",
        "Background and Related Work",
        "Methodology",
        "Results and Analysis",
        "Discussion",
        "Conclusion and Future Work",
    ])
    recommended_paper_providers: list[str] = Field(
        default_factory=lambda: ["arxiv", "semantic_scholar", "openalex", "pubmed"]
    )
    enable_citation_chaining: bool = True
    enable_deep_research: bool = True
    enable_gap_analysis: bool = True
    enable_comparison_table: bool = True
    venue: str | None = None
    venue_type: str | None = None
    tags: list[str] = Field(default_factory=list)


class TemplateUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    default_depth: str | None = None
    default_max_iterations: int | None = None
    default_max_papers_per_section: int | None = None
    default_autonomy: str | None = None
    default_latex_template: str | None = None
    default_columns: int | None = None
    default_language: str | None = None
    sections: list[str] | None = None
    recommended_paper_providers: list[str] | None = None
    enable_citation_chaining: bool | None = None
    enable_deep_research: bool | None = None
    enable_gap_analysis: bool | None = None
    enable_comparison_table: bool | None = None
    venue: str | None = None
    venue_type: str | None = None
    tags: list[str] | None = None


class PresetCreateRequest(BaseModel):
    preset_id: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(..., min_length=1, max_length=128)
    venue: str = ""
    venue_type: str = "conference"
    latex_template: str = "ieee-2col"
    columns: int = 2
    paper_providers_mode: str = "standard"
    description: str = ""
    icon: str = "🎯"
    recommended_depth: str = "balanced"
    tags: list[str] = Field(default_factory=list)


class PresetUpdateRequest(BaseModel):
    name: str | None = None
    venue: str | None = None
    venue_type: str | None = None
    latex_template: str | None = None
    columns: int | None = None
    paper_providers_mode: str | None = None
    description: str | None = None
    icon: str | None = None
    recommended_depth: str | None = None
    tags: list[str] | None = None


class ApplyTemplateRequest(BaseModel):
    template_id: str
    preset_id: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


# ── Lazy imports for template_library functions ─────────────

def _get_templates() -> Any:
    from research_agent.output.template_library import (
        list_templates, get_template, create_template,
        update_template, delete_template,
    )
    return list_templates, get_template, create_template, update_template, delete_template


def _get_presets() -> Any:
    from research_agent.output.template_library import (
        list_presets, get_preset, create_preset, delete_preset,
    )
    return list_presets, get_preset, create_preset, delete_preset


def _get_apply() -> Any:
    from research_agent.output.template_library import (
        apply_template_to_state, apply_preset_to_state, get_merged_template_config,
    )
    return apply_template_to_state, apply_preset_to_state, get_merged_template_config


# ── Template Endpoints ──────────────────────────────────────

@router.get("")
async def list_all_templates(
    category: str | None = None,
    user: User = Depends(current_active_user),
):
    """List all available research templates, optionally filtered by category."""
    list_templates, *_ = _get_templates()
    templates = list_templates()

    if category:
        templates = [t for t in templates if t.get("category") == category]

    return {"templates": templates, "count": len(templates)}


@router.get("/categories")
async def list_template_categories(
    user: User = Depends(current_active_user),
):
    """List all template categories with counts."""
    list_templates, *_ = _get_templates()
    templates = list_templates()

    from collections import Counter
    categories = Counter(t.get("category", "other") for t in templates)

    return {
        "categories": [
            {"id": cat, "name": cat.replace("_", " ").title(), "count": count}
            for cat, count in categories.most_common()
        ]
    }


@router.get("/{template_id}")
async def get_template_by_id(
    template_id: str,
    user: User = Depends(current_active_user),
):
    """Get a single template by ID."""
    _, get_template, *_ = _get_templates()
    tpl = get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return tpl


@router.post("")
async def create_custom_template(
    req: TemplateCreateRequest,
    user: User = Depends(current_active_user),
):
    """Create a new custom research template."""
    _, get_template_fn, create_template, *_ = _get_templates()
    existing = get_template_fn(req.template_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Template '{req.template_id}' already exists. Use PUT to update.",
        )

    try:
        created = create_template(req.model_dump())
        return {"success": True, "template": created}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create template: {exc}")


@router.put("/{template_id}")
async def update_custom_template(
    template_id: str,
    req: TemplateUpdateRequest,
    user: User = Depends(current_active_user),
):
    """Update an existing custom template."""
    *_, update_template, _ = _get_templates()

    # Only non-None updates
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    updated = update_template(template_id, updates)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Custom template '{template_id}' not found. Built-in templates cannot be modified.",
        )

    return {"success": True, "template": updated}


@router.delete("/{template_id}")
async def delete_custom_template(
    template_id: str,
    user: User = Depends(current_active_user),
):
    """Delete a custom template."""
    *_, _, delete_template_fn = _get_templates()
    deleted = delete_template_fn(template_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Custom template '{template_id}' not found. Built-in templates cannot be deleted.",
        )
    return {"success": True, "template_id": template_id}


# ── Preset Endpoints ─────────────────────────────────────────

@router.get("/presets")
async def list_all_presets(
    venue_type: str | None = None,
    user: User = Depends(current_active_user),
):
    """List all available conference presets, optionally filtered by venue type."""
    list_presets_fn, *_ = _get_presets()
    presets = list_presets_fn()

    if venue_type:
        presets = [p for p in presets if p.get("venue_type") == venue_type]

    return {"presets": presets, "count": len(presets)}


@router.get("/presets/{preset_id}")
async def get_preset_by_id(
    preset_id: str,
    user: User = Depends(current_active_user),
):
    """Get a single preset by ID."""
    _, get_preset_fn, *_ = _get_presets()
    prs = get_preset_fn(preset_id)
    if prs is None:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
    return prs


@router.post("/presets")
async def create_custom_preset(
    req: PresetCreateRequest,
    user: User = Depends(current_active_user),
):
    """Create a new custom conference preset."""
    _, _, create_preset_fn, _ = _get_presets()

    try:
        created = create_preset_fn(req.model_dump())
        return {"success": True, "preset": created}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create preset: {exc}")


@router.put("/presets/{preset_id}")
async def update_custom_preset(
    preset_id: str,
    req: PresetUpdateRequest,
    user: User = Depends(current_active_user),
):
    """Update an existing custom conference preset."""
    list_presets_fn, get_preset_fn, create_preset_fn, delete_preset_fn = _get_presets()

    existing = get_preset_fn(preset_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Preset '{preset_id}' not found.",
        )

    # Only non-None updates
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    # Update by re-creating with merged data
    merged = {**existing, **updates}
    merged.pop("preset_id", None)

    # Delete old and create new
    delete_preset_fn(preset_id)
    created = create_preset_fn({"preset_id": preset_id, **merged})

    return {"success": True, "preset": created}


@router.delete("/presets/{preset_id}")
async def delete_custom_preset(
    preset_id: str,
    user: User = Depends(current_active_user),
):
    """Delete a custom preset."""
    *_, _, delete_preset_fn = _get_presets()
    deleted = delete_preset_fn(preset_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Custom preset '{preset_id}' not found. Built-in presets cannot be deleted.",
        )
    return {"success": True, "preset_id": preset_id}


# ── Application Endpoints ───────────────────────────────────

@router.post("/apply")
async def apply_template_and_preset(
    req: ApplyTemplateRequest,
    user: User = Depends(current_active_user),
):
    """Apply a template (and optional preset) to get state configuration overrides.

    Returns the merged configuration that can be used to initialize a WorkflowState.
    Priority: manual overrides > preset > template > defaults.
    """
    apply_template, apply_preset, get_merged = _get_apply()

    try:
        config = get_merged(
            template_id=req.template_id,
            preset_id=req.preset_id,
            manual_overrides=req.overrides or None,
        )
        return {"success": True, "config": config}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to apply template config: {exc}")


@router.post("/{template_id}/preview")
async def preview_template_config(
    template_id: str,
    body: dict = Body(default={}),
    user: User = Depends(current_active_user),
):
    """Preview the configuration that a template would produce.

    Useful for showing users the sections, depth, and output format
    that a template will generate before starting a research run.
    """
    apply_template_fn, *_ = _get_apply()

    try:
        config = apply_template_fn(template_id, state_overrides=body.get("overrides"))
        return {"success": True, "config": config}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to preview template: {exc}")


# ── Template Library Stats ──────────────────────────────────

@router.get("/stats/summary")
async def get_template_library_stats(
    user: User = Depends(current_active_user),
):
    """Get summary statistics about the template library."""
    list_templates, *_ = _get_templates()
    list_presets_fn, *_ = _get_presets()

    templates = list_templates()
    presets = list_presets_fn()

    from collections import Counter
    categories = Counter(t.get("category", "other") for t in templates)

    return {
        "total_templates": len(templates),
        "builtin_templates": sum(1 for t in templates if t.get("id") in [
            "standard", "literature_survey", "meta_analysis", "systematic_review",
            "case_study"
        ]),
        "custom_templates": sum(1 for t in templates if t.get("id") not in [
            "standard", "literature_survey", "meta_analysis", "systematic_review",
            "case_study"
        ]),
        "total_presets": len(presets),
        "categories": [
            {"id": cat, "count": count}
            for cat, count in categories.most_common()
        ],
    }
