"""P19: Plugin System — Base plugin class with lifecycle hooks.

All plugins must subclass BasePlugin and implement the hooks they need.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class HookResult:
    """Result returned by a plugin hook execution."""

    def __init__(
        self,
        plugin_id: str,
        hook_name: str,
        success: bool = True,
        data: dict[str, Any] | None = None,
        error: str | None = None,
    ):
        self.plugin_id = plugin_id
        self.hook_name = hook_name
        self.success = success
        self.data = data or {}
        self.error = error


class PluginMetadata(BaseModel):
    """Metadata about a registered plugin."""
    id: str
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    homepage: str = ""
    tags: list[str] = Field(default_factory=list)
    enabled_by_default: bool = True
    requires_sandbox: bool = False
    hooks_implemented: list[str] = Field(default_factory=list)


class BasePlugin(ABC):
    """Abstract base class for all research-agent plugins.

    Subclass this and implement any hooks you need.
    Register your plugin via `pyproject.toml` entry points or place it
    in `src/research_agent/plugins/installed/`.
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return metadata about this plugin."""
        ...

    # ── Lifecycle Hooks ──────────────────────────────────────

    async def on_run_start(self, run_id: str, topic: str, **kwargs: Any) -> HookResult:
        """Called when a new research run starts.

        Args:
            run_id: The unique run identifier.
            topic: The research topic/question.
            kwargs: Additional context (template, depth, settings, etc.)

        Returns:
            HookResult with optional data dict to inject into graph state.
        """
        return HookResult(
            plugin_id=self.metadata.id,
            hook_name="on_run_start",
            success=True,
        )

    async def on_section_generated(
        self,
        section_title: str,
        section_content: str,
        section_confidence: float,
        run_id: str,
        **kwargs: Any,
    ) -> HookResult:
        """Called when a section of the paper is generated.

        Args:
            section_title: The section heading.
            section_content: The LaTeX content of the section.
            section_confidence: Confidence score (0.0-1.0).
            run_id: The unique run identifier.
            kwargs: Additional context.

        Returns:
            HookResult with optional data to inject into graph state.
        """
        return HookResult(
            plugin_id=self.metadata.id,
            hook_name="on_section_generated",
            success=True,
        )

    async def on_run_complete(
        self,
        run_id: str,
        latex_main: str,
        bibtex: str,
        **kwargs: Any,
    ) -> HookResult:
        """Called when a research run completes.

        Args:
            run_id: The unique run identifier.
            latex_main: The generated LaTeX document.
            bibtex: The generated bibliography.
            kwargs: Additional context (sections, citations, artifact_dir, etc.)

        Returns:
            HookResult with optional data for post-processing.
        """
        return HookResult(
            plugin_id=self.metadata.id,
            hook_name="on_run_complete",
            success=True,
        )

    async def on_error(
        self,
        run_id: str,
        error: str,
        phase: str,
        **kwargs: Any,
    ) -> HookResult:
        """Called when an error occurs during a research run.

        Args:
            run_id: The unique run identifier.
            error: The error message.
            phase: The graph phase where the error occurred.
            kwargs: Additional context.

        Returns:
            HookResult with optional recovery data.
        """
        return HookResult(
            plugin_id=self.metadata.id,
            hook_name="on_error",
            success=True,
        )

    async def on_step(
        self,
        run_id: str,
        step: str,
        status: str,
        **kwargs: Any,
    ) -> HookResult:
        """Called for each step/progress update during a run.

        Args:
            run_id: The unique run identifier.
            step: The current step name (e.g. "planning", "researching", "writing").
            status: The step status (e.g. "started", "in_progress", "completed").
            kwargs: Additional context.

        Returns:
            HookResult.
        """
        return HookResult(
            plugin_id=self.metadata.id,
            hook_name="on_step",
            success=True,
        )

    def get_settings_schema(self) -> dict[str, Any] | None:
        """Return a JSON Schema dict for plugin-specific settings.

        If the plugin has user-configurable settings, return a JSON Schema
        that the UI can render as a settings form.
        """
        return None

    def get_ui_components(self) -> list[dict[str, Any]] | None:
        """Return UI component definitions for the plugin browser.

        Each component dict can have:
        - type: "panel", "button", "chart", "table"
        - title: Display title
        - render: Custom renderer key (for frontend)
        """
        return None
