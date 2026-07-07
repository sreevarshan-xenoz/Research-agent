"""P19: Plugin System — Plugin lifecycle manager.

Manages plugin registration, enable/disable state, and
orchestrates hook execution across all enabled plugins.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from research_agent.plugins.base import BasePlugin, HookResult
from research_agent.plugins.discovery import discover_all_plugins
from research_agent.plugins.sandbox import run_in_sandbox

logger = logging.getLogger(__name__)


class PluginManager:
    """Central plugin manager that handles discovery, state, and hook execution.

    Usage::

        manager = PluginManager()
        manager.discover()
        await manager.run_hook("on_run_start", run_id="...", topic="...")
    """

    def __init__(self, settings_path: str | None = None):
        self._plugins: dict[str, BasePlugin] = {}
        self._enabled: set[str] = set()
        self._settings_path = Path(settings_path or ".runtime/plugins_state.json")
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_state()

    # ── Discovery ──────────────────────────────────────────────────────────

    def discover(self, plugin_dirs: list[str] | None = None) -> dict[str, BasePlugin]:
        """Discover and register all available plugins."""
        discovered = discover_all_plugins(plugin_dirs)
        self._plugins.update(discovered)

        # Auto-enable new plugins (if they have enabled_by_default=True)
        for pid, plugin in self._plugins.items():
            if pid not in self._enabled and plugin.metadata.enabled_by_default:
                self._enabled.add(pid)

        self._save_state()
        logger.info("Discovered %d plugins, %d enabled", len(self._plugins), len(self._enabled))
        return self._plugins

    # ── Plugin state ───────────────────────────────────────────────────────

    def list_plugins(self) -> list[dict[str, Any]]:
        """Return all plugins with their metadata and enabled status."""
        return [
            {
                "id": pid,
                "metadata": plugin.metadata.model_dump(),
                "enabled": pid in self._enabled,
                "settings_schema": plugin.get_settings_schema(),
                "ui_components": plugin.get_ui_components(),
            }
            for pid, plugin in sorted(self._plugins.items())
        ]

    def get_plugin(self, plugin_id: str) -> BasePlugin | None:
        return self._plugins.get(plugin_id)

    def is_enabled(self, plugin_id: str) -> bool:
        return plugin_id in self._enabled and plugin_id in self._plugins

    def enable_plugin(self, plugin_id: str) -> bool:
        if plugin_id in self._plugins:
            self._enabled.add(plugin_id)
            self._save_state()
            return True
        return False

    def disable_plugin(self, plugin_id: str) -> bool:
        self._enabled.discard(plugin_id)
        self._save_state()
        return True

    def set_plugin_setting(self, plugin_id: str, key: str, value: Any) -> bool:
        """Set a plugin-specific setting (persisted to disk)."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        state = self._load_settings_dict()
        if plugin_id not in state:
            state[plugin_id] = {}
        state[plugin_id][key] = value
        self._save_settings_dict(state)
        return True

    def get_plugin_settings(self, plugin_id: str) -> dict[str, Any]:
        state = self._load_settings_dict()
        return state.get(plugin_id, {})

    # ── Hook execution ─────────────────────────────────────────────────────

    async def run_hook(
        self,
        hook_name: str,
        **kwargs: Any,
    ) -> list[HookResult]:
        """Run a lifecycle hook across all enabled plugins that implement it.

        Args:
            hook_name: One of "on_run_start", "on_section_generated",
                      "on_run_complete", "on_error", "on_step".
            kwargs: Arguments passed to the hook method.

        Returns:
            List of HookResult objects, one per plugin that executed the hook.
        """
        results: list[HookResult] = []
        for pid, plugin in self._plugins.items():
            if pid not in self._enabled:
                continue

            # Check if the plugin implements this hook
            hook_method = getattr(plugin, hook_name, None)
            if hook_method is None:
                continue

            # Skip the default no-op implementations (empty HookResult)
            method = getattr(type(plugin), hook_name, None)
            if method is BasePlugin.__dict__.get(hook_name):
                continue

            try:
                if plugin.metadata.requires_sandbox:
                    result = await run_in_sandbox(hook_method, **kwargs)
                else:
                    result = await hook_method(**kwargs)

                if not isinstance(result, HookResult):
                    result = HookResult(
                        plugin_id=pid,
                        hook_name=hook_name,
                        success=True,
                        data={"raw": result},
                    )
                results.append(result)

                if not result.success:
                    logger.warning(
                        "Plugin '%s' hook '%s' failed: %s",
                        plugin.metadata.name, hook_name, result.error,
                    )
                else:
                    logger.debug(
                        "Plugin '%s' hook '%s' succeeded",
                        plugin.metadata.name, hook_name,
                    )

            except Exception as exc:
                logger.error(
                    "Plugin '%s' hook '%s' raised: %s",
                    plugin.metadata.name, hook_name, exc,
                )
                results.append(HookResult(
                    plugin_id=pid,
                    hook_name=hook_name,
                    success=False,
                    error=str(exc),
                ))

        return results

    async def run_hook_aggregated(
        self,
        hook_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run a hook and aggregate all plugin data into a single dict.

        Useful for hooks that inject data into graph state:

            data = await manager.run_hook_aggregated("on_run_start", ...)
            state.update(data)
        """
        results = await self.run_hook(hook_name, **kwargs)
        aggregated: dict[str, Any] = {}
        for r in results:
            if r.success and r.data:
                # Collect plugin-specific data under plugin_id keys
                aggregated[f"plugin_{r.plugin_id}"] = r.data
        return aggregated

    # ── Persistence ────────────────────────────────────────────────────────

    def _state_path(self) -> Path:
        return self._settings_path

    def _load_state(self) -> None:
        try:
            if self._state_path().exists():
                data = json.loads(self._state_path().read_text(encoding="utf-8"))
                self._enabled = set(data.get("enabled", []))
        except Exception as exc:
            logger.warning("Failed to load plugin state: %s", exc)
            self._enabled = set()

    def _save_state(self) -> None:
        try:
            data = {"enabled": list(self._enabled)}
            self._state_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to save plugin state: %s", exc)

    def _load_settings_dict(self) -> dict[str, dict[str, Any]]:
        settings_file = self._state_path().parent / "plugin_settings.json"
        if not settings_file.exists():
            return {}
        try:
            return json.loads(settings_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_settings_dict(self, state: dict[str, dict[str, Any]]) -> None:
        settings_file = self._state_path().parent / "plugin_settings.json"
        try:
            settings_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to save plugin settings: %s", exc)


# ── Module-level singleton ─────────────────────────────────────────────────

_manager_instance: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get or create the module-level PluginManager singleton."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = PluginManager()
        _manager_instance.discover()
    return _manager_instance


def reset_plugin_manager() -> None:
    """Reset the plugin manager singleton (useful for testing)."""
    global _manager_instance
    _manager_instance = None
