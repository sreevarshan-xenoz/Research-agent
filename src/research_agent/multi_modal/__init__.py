from __future__ import annotations

from research_agent.multi_modal.figure_extractor import (
    extract_figures_from_pdf,
    generate_figure_caption,
    ExtractedFigure,
)
from research_agent.multi_modal.table_extractor import (
    extract_tables_from_pdf_visual,
    ExtractedTable,
)
from research_agent.multi_modal.equation_extractor import (
    extract_equations_from_pdf,
    normalize_equation,
    ExtractedEquation,
)
from research_agent.multi_modal.chart_reader import (
    describe_chart_from_image,
    ChartDescription,
)
from research_agent.multi_modal.qa_engine import (
    MultiModalQA,
    MultiModalQAEngine,
    QAResult,
)
from research_agent.multi_modal.pipeline import (
    run_multi_modal_pipeline,
    MultiModalResult,
)

__all__ = [
    "extract_figures_from_pdf",
    "generate_figure_caption",
    "ExtractedFigure",
    "extract_tables_from_pdf_visual",
    "ExtractedTable",
    "extract_equations_from_pdf",
    "normalize_equation",
    "ExtractedEquation",
    "describe_chart_from_image",
    "ChartDescription",
    "MultiModalQA",
    "MultiModalQAEngine",
    "QAResult",
    "run_multi_modal_pipeline",
    "MultiModalResult",
]
