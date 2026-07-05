"""Orchestrator for the full multi-modal extraction pipeline.

Runs figure extraction, table parsing, equation extraction, and
chart description generation on a given PDF, returning a unified
result object.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from research_agent.multi_modal.figure_extractor import (
    ExtractedFigure,
    extract_figures_from_pdf,
    generate_figure_caption,
)
from research_agent.multi_modal.table_extractor import (
    ExtractedTable,
    extract_tables_from_pdf_visual,
)
from research_agent.multi_modal.equation_extractor import (
    ExtractedEquation,
    extract_equations_from_pdf,
)
from research_agent.multi_modal.chart_reader import (
    ChartDescription,
    describe_chart_from_image,
)

logger = logging.getLogger(__name__)


class MultiModalResult:
    """Aggregated result from running the full multi-modal pipeline."""

    def __init__(
        self,
        figures: list[ExtractedFigure] | None = None,
        tables: list[ExtractedTable] | None = None,
        equations: list[ExtractedEquation] | None = None,
        chart_descriptions: list[ChartDescription] | None = None,
    ) -> None:
        self.figures = figures or []
        self.tables = tables or []
        self.equations = equations or []
        self.chart_descriptions = chart_descriptions or []

    @property
    def figure_count(self) -> int:
        return len(self.figures)

    @property
    def table_count(self) -> int:
        return len(self.tables)

    @property
    def equation_count(self) -> int:
        return len(self.equations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "figures": [f.to_dict() for f in self.figures],
            "tables": [t.to_dict() for t in self.tables],
            "equations": [e.to_dict() for e in self.equations],
            "chart_descriptions": [c.to_dict() for c in self.chart_descriptions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MultiModalResult:
        return cls(
            figures=[ExtractedFigure.from_dict(f) for f in data.get("figures", [])],
            tables=[ExtractedTable.from_dict(t) for t in data.get("tables", [])],
            equations=[ExtractedEquation.from_dict(e) for e in data.get("equations", [])],
            chart_descriptions=[ChartDescription.from_dict(c) for c in data.get("chart_descriptions", [])],
        )


async def run_multi_modal_pipeline(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
    extract_figures: bool = True,
    extract_tables: bool = True,
    extract_equations: bool = True,
    generate_chart_descriptions: bool = True,
    generate_captions: bool = True,
    max_figures: int = 20,
    max_tables: int = 30,
    max_equations: int = 50,
) -> MultiModalResult:
    """Run the full multi-modal extraction pipeline on a PDF.

    Orchestrates figure extraction, table parsing, equation extraction,
    and chart description generation in parallel where possible.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to save extracted artifacts (images, etc.).
        extract_figures: Whether to extract figures.
        extract_tables: Whether to extract tables.
        extract_equations: Whether to extract equations.
        generate_chart_descriptions: Whether to generate chart descriptions.
        generate_captions: Whether to generate figure captions via LLM.
        max_figures: Max figures to extract.
        max_tables: Max tables to extract.
        max_equations: Max equations to extract.

    Returns:
        MultiModalResult with all extracted content.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    import asyncio

    tasks = []

    # Figure extraction + captioning
    if extract_figures:
        async def _do_figures() -> tuple[list[ExtractedFigure], list[ChartDescription]]:
            figs = await extract_figures_from_pdf(
                pdf_path=pdf_path,
                output_dir=output_dir,
                max_figures=max_figures,
            )
            descriptions: list[ChartDescription] = []
            if generate_chart_descriptions and figs:
                desc_tasks = []
                for fig in figs[:5]:  # Limit to first 5 for cost
                    if fig.image_path:
                        desc_tasks.append(
                            describe_chart_from_image(
                                image_path=fig.image_path,
                            )
                        )
                    else:
                        desc_tasks.append(
                            describe_chart_from_image(
                                image_path=fig.image_path if fig.image_path else "",
                            )
                        )
                if desc_tasks:
                    descriptions = await asyncio.gather(*desc_tasks, return_exceptions=True)
                    descriptions = [d for d in descriptions if isinstance(d, ChartDescription)]

            # Generate captions for figures that have image paths
            if generate_captions and figs:
                fig_cap_pairs = [(fig, fig.image_path) for fig in figs[:5] if fig.image_path]
                if fig_cap_pairs:
                    cap_tasks = [generate_figure_caption(image_path=path) for _, path in fig_cap_pairs]
                    captions = await asyncio.gather(*cap_tasks, return_exceptions=True)
                    for (fig, _), cap in zip(fig_cap_pairs, captions):
                        if isinstance(cap, str):
                            fig.caption = cap

            return figs, descriptions

        tasks.append(_do_figures())
    else:
        tasks.append(async_noop([]))

    # Table extraction
    if extract_tables:
        tasks.append(extract_tables_from_pdf_visual(pdf_path=pdf_path, max_tables=max_tables))
    else:
        tasks.append(async_noop([]))

    # Equation extraction
    if extract_equations:
        tasks.append(extract_equations_from_pdf(pdf_path=pdf_path, output_dir=output_dir, max_equations=max_equations))
    else:
        tasks.append(async_noop([]))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    figures: list[ExtractedFigure] = []
    chart_descriptions: list[ChartDescription] = []
    tables: list[ExtractedTable] = []
    equations: list[ExtractedEquation] = []

    for r in results:
        if isinstance(r, Exception):
            logger.error("Multi-modal pipeline sub-task failed: %s", r)
            continue
        if isinstance(r, tuple):
            figures, chart_descriptions = r
        elif isinstance(r, list):
            # Determine type from first element
            if r and isinstance(r[0], ExtractedTable):
                tables = r
            elif r and isinstance(r[0], ExtractedEquation):
                equations = r

    return MultiModalResult(
        figures=figures,
        tables=tables,
        equations=equations,
        chart_descriptions=chart_descriptions,
    )


async def async_noop(result: Any = None) -> Any:
    return result
