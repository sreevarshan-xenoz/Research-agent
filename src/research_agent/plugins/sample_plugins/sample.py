"""Sample plugins demonstrating the P19 Plugin System.

Each plugin is a BasePlugin subclass that implements one or more
lifecycle hooks. These are auto-discovered via filesystem scanning.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from research_agent.plugins.base import BasePlugin, HookResult, PluginMetadata

logger = logging.getLogger(__name__)


class RunStatsLoggerPlugin(BasePlugin):
    """Logs research run statistics (duration, sections, citations) to a JSON file."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="run_stats_logger",
            name="Run Stats Logger",
            version="1.0.0",
            description="Logs research run statistics (duration, sections, citations) to a JSON file for later analysis.",
            author="Research Agent",
            tags=["logging", "stats", "analytics"],
            enabled_by_default=True,
            hooks_implemented=["on_run_start", "on_run_complete"],
        )

    async def on_run_start(self, run_id: str, topic: str, **kwargs: Any) -> HookResult:
        log_path = Path(f".runtime/plugin_logs/{run_id}")
        log_path.mkdir(parents=True, exist_ok=True)
        (log_path / "run_start.json").write_text(
            json.dumps({
                "run_id": run_id,
                "topic": topic,
                "started_at": datetime.utcnow().isoformat() + "Z",
                "template": kwargs.get("template", "ieee"),
                "depth": kwargs.get("depth", "balanced"),
            }, indent=2),
            encoding="utf-8",
        )
        return HookResult(
            plugin_id=self.metadata.id,
            hook_name="on_run_start",
            success=True,
            data={"run_start_logged": True},
        )

    async def on_run_complete(self, run_id: str, latex_main: str, bibtex: str, **kwargs: Any) -> HookResult:
        log_path = Path(f".runtime/plugin_logs/{run_id}")
        log_path.mkdir(parents=True, exist_ok=True)

        section_count = latex_main.count("\\section{") if latex_main else 0
        citation_count = latex_main.count("\\cite{") if latex_main else 0
        word_count = len(latex_main.split()) if latex_main else 0

        stats = {
            "run_id": run_id,
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "section_count": section_count,
            "citation_count": citation_count,
            "word_count": word_count,
            "has_bibtex": bool(bibtex),
        }
        (log_path / "run_complete.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        logger.info("Run %s: %d sections, %d citations, %d words", run_id, section_count, citation_count, word_count)

        return HookResult(
            plugin_id=self.metadata.id,
            hook_name="on_run_complete",
            success=True,
            data=stats,
        )

    def get_settings_schema(self) -> dict | None:
        return {
            "type": "object",
            "properties": {
                "log_dir": {
                    "type": "string",
                    "description": "Directory to store run logs",
                    "default": ".runtime/plugin_logs",
                },
            },
        }


class CitationCounterPlugin(BasePlugin):
    """Counts and categorises citations in generated sections."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="citation_counter",
            name="Citation Counter",
            version="1.0.0",
            description="Counts and categorises citations in generated sections, tracking citation freshness.",
            author="Research Agent",
            tags=["citations", "metrics"],
            enabled_by_default=True,
            hooks_implemented=["on_section_generated"],
        )

    async def on_section_generated(
        self,
        section_title: str,
        section_content: str,
        section_confidence: float,
        run_id: str,
        **kwargs: Any,
    ) -> HookResult:
        import re
        citations = re.findall(r"\\cite\{([^}]+)\}", section_content)
        # Flatten comma-separated citations within a single \cite{}
        flat_citations: list[str] = []
        for c in citations:
            for single in c.split(","):
                flat_citations.append(single.strip())

        return HookResult(
            plugin_id=self.metadata.id,
            hook_name="on_section_generated",
            success=True,
            data={
                "section": section_title,
                "citation_count": len(flat_citations),
                "citations": flat_citations,
            },
        )

    def get_ui_components(self) -> list[dict] | None:
        return [
            {
                "type": "table",
                "title": "Citation Counts by Section",
                "render": "citation_table",
            },
        ]


# Module-level instances for auto-discovery
# The discovery module looks for `plugin` attribute AND scans all BasePlugin subclasses
plugin = RunStatsLoggerPlugin()
_plugins_list = [RunStatsLoggerPlugin(), CitationCounterPlugin()]


def register_plugin() -> BasePlugin:
    """Return the primary plugin instance (for entry-point registration)."""
    return RunStatsLoggerPlugin()


def register_all_plugins() -> list[BasePlugin]:
    """Return all sample plugins (for programmatic registration)."""
    return [RunStatsLoggerPlugin(), CitationCounterPlugin()]
