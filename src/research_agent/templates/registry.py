from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_agent.templates.models import (
    ResearchTemplate,
    _BUILTIN_TEMPLATES,
)

# Module-level cache for custom user templates loaded from disk.
_custom_templates: dict[str, ResearchTemplate] | None = None


def get_template(template_id: str) -> ResearchTemplate | None:
    """Retrieve a template by ID, checking custom templates first."""
    # Check built-in templates
    if template_id in _BUILTIN_TEMPLATES:
        return _BUILTIN_TEMPLATES[template_id]

    # Check custom (user-created) templates
    custom = _load_custom_templates()
    if template_id in custom:
        return custom[template_id]

    return None


def list_templates() -> list[ResearchTemplate]:
    """Return all available templates (built-in + custom)."""
    templates = list(_BUILTIN_TEMPLATES.values())
    custom = _load_custom_templates()
    templates.extend(custom.values())
    return templates


def get_default_template() -> ResearchTemplate:
    """Return the default template (Standard)."""
    return _BUILTIN_TEMPLATES["standard"]


def add_custom_template(template: ResearchTemplate, store_path: str | Path = ".runtime/templates.json") -> None:
    """Persist a custom/user-created template to disk."""
    global _custom_templates
    path = Path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing custom templates
    custom = _load_custom_templates_from_path(path)
    custom[template.id] = template

    # Save
    data = {tid: t.to_dict() for tid, t in custom.items()}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Update cache
    _custom_templates = custom


def remove_custom_template(template_id: str, store_path: str | Path = ".runtime/templates.json") -> bool:
    """Remove a custom template by ID. Returns True if removed."""
    global _custom_templates
    path = Path(store_path)
    if not path.exists():
        return False

    custom = _load_custom_templates_from_path(path)
    if template_id not in custom:
        return False

    del custom[template_id]
    data = {tid: t.to_dict() for tid, t in custom.items()}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _custom_templates = custom
    return True


def _load_custom_templates() -> dict[str, ResearchTemplate]:
    """Load custom templates from the default store path (cached)."""
    global _custom_templates
    if _custom_templates is not None:
        return _custom_templates

    # Try to determine store path from settings
    try:
        from research_agent.config import load_settings
        settings = load_settings()
        store_path = settings.template_library.store_path
    except Exception:
        store_path = ".runtime/templates.json"

    _custom_templates = _load_custom_templates_from_path(Path(store_path))
    return _custom_templates


def _load_custom_templates_from_path(path: Path) -> dict[str, ResearchTemplate]:
    """Load custom templates from a specific path (no caching)."""
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {
            tid: ResearchTemplate.from_dict(item)
            for tid, item in data.items()
            if isinstance(item, dict)
        }
    except (json.JSONDecodeError, OSError):
        return {}
