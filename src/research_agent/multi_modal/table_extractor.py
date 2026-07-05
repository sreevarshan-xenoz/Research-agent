"""Visual table extraction from PDFs using pdfplumber."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExtractedTable:
    """Represents a single table extracted from a PDF page."""

    def __init__(
        self,
        page: int,
        header: list[str],
        rows: list[list[str]],
        caption: str | None = None,
    ) -> None:
        self.page = page
        self.header = header
        self.rows = rows
        self.caption = caption

    def to_markdown(self) -> str:
        """Render the table as a GitHub-Flavored Markdown table."""
        if not self.header and not self.rows:
            return "(empty table)"

        lines: list[str] = []
        if self.caption:
            lines.append(f"**{self.caption}**  ")
            lines.append("")

        if self.header:
            lines.append("| " + " | ".join(self.header) + " |")
            lines.append("| " + " | ".join("---" for _ in self.header) + " |")
            for row in self.rows:
                padded = row + [""] * (len(self.header) - len(row))
                lines.append("| " + " | ".join(padded) + " |")
        else:
            for row in self.rows:
                lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "header": self.header,
            "rows": self.rows,
            "caption": self.caption,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedTable:
        return cls(
            page=data["page"],
            header=data.get("header", []),
            rows=data.get("rows", []),
            caption=data.get("caption"),
        )


async def extract_tables_from_pdf_visual(
    pdf_path: str | Path,
    max_tables: int = 30,
) -> list[ExtractedTable]:
    """Extract tables from a PDF using pdfplumber's visual table detection.

    Identifies tables by analyzing lines and character positions on each
    page. Works best on machine-generated (not scanned) PDFs.

    Args:
        pdf_path: Path to the PDF file.
        max_tables: Maximum number of tables to extract.

    Returns:
        List of ExtractedTable objects.
    """
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("pdfplumber not installed — table extraction disabled")
        return []

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        return []

    tables: list[ExtractedTable] = []

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                if len(tables) >= max_tables:
                    break

                try:
                    page_tables = page.find_tables()
                except Exception as exc:
                    logger.debug("find_tables failed on page %d: %s", page_idx + 1, exc)
                    continue

                for tbl in page_tables:
                    if len(tables) >= max_tables:
                        break

                    data = tbl.extract()
                    if not data or len(data) < 2:
                        continue

                    header = [str(c).strip() if c else "" for c in data[0]]
                    rows = [
                        [str(c).strip() if c else "" for c in row]
                        for row in data[1:]
                    ]

                    tables.append(
                        ExtractedTable(
                            page=page_idx + 1,
                            header=header,
                            rows=rows,
                        )
                    )
    except Exception as exc:
        logger.error("Failed to extract tables: %s", exc)

    logger.info("Extracted %d tables from %s", len(tables), pdf_path)
    return tables
