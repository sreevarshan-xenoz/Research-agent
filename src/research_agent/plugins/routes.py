"""P19 — Plugin System API routes.

Endpoints cover:
- Listing all plugins with metadata and enabled status
- Enabling/disabling plugins
- Viewing plugin details (hooks, settings schema, UI components)
- Getting/setting plugin-specific settings
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from research_agent.app.auth import current_active_user, User
from research_agent.plugins.manager import get_plugin_manager

router = APIRouter(prefix="/api/plugins", tags=["Plugin System"])


@router.get("")
async def list_plugins(
    user: User = Depends(current_active_user),
) -> list[dict[str, Any]]:
    """List all discovered plugins with metadata, enabled status, and UI info."""
    manager = get_plugin_manager()
    return manager.list_plugins()


@router.get("/{plugin_id}")
async def get_plugin_detail(
    plugin_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Get detailed information about a specific plugin."""
    manager = get_plugin_manager()
    plugin = manager.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")

    return {
        "id": plugin_id,
        "metadata": plugin.metadata.model_dump(),
        "enabled": manager.is_enabled(plugin_id),
        "settings_schema": plugin.get_settings_schema(),
        "ui_components": plugin.get_ui_components(),
        "settings": manager.get_plugin_settings(plugin_id),
    }


@router.post("/{plugin_id}/enable")
async def enable_plugin(
    plugin_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Enable a plugin."""
    manager = get_plugin_manager()
    if not manager.enable_plugin(plugin_id):
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return {"success": True, "plugin_id": plugin_id, "enabled": True}


@router.post("/{plugin_id}/disable")
async def disable_plugin(
    plugin_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Disable a plugin."""
    manager = get_plugin_manager()
    manager.disable_plugin(plugin_id)
    return {"success": True, "plugin_id": plugin_id, "enabled": False}


@router.get("/{plugin_id}/settings")
async def get_plugin_settings(
    plugin_id: str,
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Get settings for a specific plugin."""
    manager = get_plugin_manager()
    if not manager.get_plugin(plugin_id):
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return manager.get_plugin_settings(plugin_id)


@router.put("/{plugin_id}/settings")
async def update_plugin_settings(
    plugin_id: str,
    body: dict[str, Any],
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Update settings for a specific plugin."""
    manager = get_plugin_manager()
    if not manager.get_plugin(plugin_id):
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")

    for key, value in body.items():
        manager.set_plugin_setting(plugin_id, key, value)

    return {"success": True, "plugin_id": plugin_id, "settings": manager.get_plugin_settings(plugin_id)}


@router.post("/discover")
async def rediscover_plugins(
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Re-discover all plugins from entry points and filesystem."""
    manager = get_plugin_manager()
    manager.discover()
    plugins = manager.list_plugins()
    return {
        "success": True,
        "total_plugins": len(plugins),
        "enabled_count": sum(1 for p in plugins if p["enabled"]),
    }
