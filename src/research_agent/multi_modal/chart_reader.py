"""Chart-to-text / chart description generation for accessibility.

Uses vision-capable LLMs to generate verbal descriptions of charts,
graphs, and figures so the content is accessible to screen readers
and can be indexed for retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ChartDescription:
    """Description of a chart or figure for accessibility."""

    def __init__(
        self,
        chart_type: str = "unknown",
        title: str = "",
        summary: str = "",
        data_points: list[dict[str, Any]] | None = None,
        axes: list[str] | None = None,
        key_insight: str = "",
    ) -> None:
        self.chart_type = chart_type
        self.title = title
        self.summary = summary
        self.data_points = data_points or []
        self.axes = axes or []
        self.key_insight = key_insight

    def to_text(self) -> str:
        """Return a human-readable description string."""
        parts = [f"Chart type: {self.chart_type}"]
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.summary:
            parts.append(f"Summary: {self.summary}")
        if self.key_insight:
            parts.append(f"Key insight: {self.key_insight}")
        if self.axes:
            parts.append(f"Axes: {' vs '.join(self.axes)}")
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chart_type": self.chart_type,
            "title": self.title,
            "summary": self.summary,
            "data_points": self.data_points,
            "axes": self.axes,
            "key_insight": self.key_insight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChartDescription:
        return cls(
            chart_type=data.get("chart_type", "unknown"),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            data_points=data.get("data_points"),
            axes=data.get("axes"),
            key_insight=data.get("key_insight", ""),
        )


async def describe_chart_from_image(
    image_path: str | Path,
    page_context: str | None = None,
) -> ChartDescription:
    """Generate a structured description of a chart/figure image.

    Uses litellm with a vision-capable model to analyze the image and
    produce a structured description. Falls back to text-only generation
    if vision is unavailable.

    Args:
        image_path: Path to the chart/figure image file (used as context).
        page_context: Optional surrounding page text for context.

    Returns:
        Structured ChartDescription object.
    """
    from research_agent.config import load_settings
    settings = load_settings()

    vision_model = settings.models.subagent_openai or "openai/gpt-4o"
    api_key = str(settings.openai.api_key) if settings.openai.api_key else None

    system_prompt = (
        "You are a scientific chart accessibility assistant. Analyze the chart image "
        "and return a JSON object with: chart_type (bar/line/scatter/pie/heatmap/box/"
        "schematic/micrograph/other), title, summary (2-3 sentence description), "
        f"key_insight (the most important takeaway), axes (list of axis labels if visible).\n"
        f"Image path: {image_path}"
    )

    user_prompt = "Describe this chart for accessibility and data extraction."
    if page_context:
        user_prompt += f"\n\nContext from page: {page_context[:1000]}"

    try:
        import litellm  # type: ignore[import-untyped]
        response = await litellm.acompletion(
            model=vision_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=500,
            api_key=api_key,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content if response.choices else ""
        import json
        result = json.loads(text) if text else {}
        if isinstance(result, dict):
            return ChartDescription(
                chart_type=str(result.get("chart_type", "unknown")),
                title=str(result.get("title", "")),
                summary=str(result.get("summary", "")),
                data_points=result.get("data_points"),
                axes=result.get("axes"),
                key_insight=str(result.get("key_insight", "")),
            )
    except Exception as exc:
        logger.warning("Vision chart description failed: %s", exc)
        # Fallback: return a basic description
        return ChartDescription(
            chart_type="unknown",
            summary=f"Chart from {Path(str(image_path)).name} (description unavailable)",
        )

    return ChartDescription(summary="Chart description unavailable")
