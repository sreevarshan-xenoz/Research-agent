"""Equation extraction & normalization from PDFs using Pix2Text (LaTeX-OCR).

Pix2Text (P2T) is an open-source Python toolkit for converting images
of mathematical expressions to LaTeX. It handles full-page layout
analysis, text recognition, and math formula recognition.

If Pix2Text is not installed, falls back to extracting equations from
PDF text content using regex heuristics.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExtractedEquation:
    """Represents a single equation extracted from a PDF."""

    def __init__(
        self,
        page: int,
        latex: str,
        source: str = "ocr",
        confidence: float | None = None,
    ) -> None:
        self.page = page
        self.latex = latex
        self.source = source  # "ocr", "text", or "regex"
        self.confidence = confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "latex": self.latex,
            "source": self.source,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedEquation:
        return cls(
            page=data["page"],
            latex=data["latex"],
            source=data.get("source", "ocr"),
            confidence=data.get("confidence"),
        )


async def extract_equations_from_pdf(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
    max_equations: int = 50,
    use_pix2text: bool = True,
) -> list[ExtractedEquation]:
    """Extract mathematical equations from a PDF.

    First attempts Pix2Text (LaTeX-OCR) if available. Falls back to
    regex-based extraction from the PDF's text content.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to save equation images (for Pix2Text).
        max_equations: Maximum number of equations to extract.
        use_pix2text: Whether to attempt Pix2Text-based OCR extraction.

    Returns:
        List of ExtractedEquation objects.
    """
    equations: list[ExtractedEquation] = []

    if use_pix2text:
        eqs = await _extract_with_pix2text(pdf_path, output_dir, max_equations)
        equations.extend(eqs)

    if not equations:
        eqs = await _extract_equations_from_text(pdf_path, max_equations)
        equations.extend(eqs)

    logger.info("Extracted %d equations from %s", len(equations), pdf_path)
    return equations


async def _extract_with_pix2text(
    pdf_path: Path,
    output_dir: Path | None,
    max_equations: int,
) -> list[ExtractedEquation]:
    """Use Pix2Text to recognize equations from rendered PDF pages."""
    equations: list[ExtractedEquation] = []

    try:
        from pix2text import Pix2Text  # type: ignore[import-untyped]
    except ImportError:
        logger.info("Pix2Text not installed — falling back to text extraction")
        return equations

    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError:
        return equations

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return equations

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    try:
        p2t = Pix2Text()
    except Exception as exc:
        logger.warning("Failed to initialize Pix2Text: %s", exc)
        return equations

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return equations

    for page_num in range(len(doc)):
        if len(equations) >= max_equations:
            break

        page = doc[page_num]

        # Render page to image for Pix2Text
        try:
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")

            result = p2t.recognize(img_bytes)
        except Exception as exc:
            logger.debug("Pix2Text failed on page %d: %s", page_num + 1, exc)
            continue

        if isinstance(result, list):
            for item in result:
                if len(equations) >= max_equations:
                    break
                if isinstance(item, dict):
                    latex = item.get("latex") or item.get("text", "")
                    conf = item.get("confidence")
                    if latex and "\\" in latex:
                        equations.append(
                            ExtractedEquation(
                                page=page_num + 1,
                                latex=latex.strip(),
                                source="ocr",
                                confidence=conf,
                            )
                        )
        elif isinstance(result, str):
            # Single text result — extract equations via regex
            eqs = _find_latex_in_text(result)
            for eq in eqs:
                if len(equations) >= max_equations:
                    break
                equations.append(
                    ExtractedEquation(
                        page=page_num + 1,
                        latex=eq,
                        source="ocr",
                    )
                )

    doc.close()
    return equations


async def _extract_equations_from_text(
    pdf_path: Path,
    max_equations: int,
) -> list[ExtractedEquation]:
    """Extract equations from PDF text content using regex heuristics."""
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError:
        return []

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return []

    equations: list[ExtractedEquation] = []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return []

    for page_num in range(len(doc)):
        if len(equations) >= max_equations:
            break
        try:
            text = doc[page_num].get_text("text")
            found = _find_latex_in_text(text)
            for eq in found:
                if len(equations) >= max_equations:
                    break
                equations.append(
                    ExtractedEquation(
                        page=page_num + 1,
                        latex=eq,
                        source="text",
                    )
                )
        except Exception:
            continue

    doc.close()
    return equations


_LATEX_PATTERNS = [
    re.compile(r"\$\$(.+?)\$\$", re.DOTALL),       # $$ ... $$
    re.compile(r"\$(.+?)\$"),                         # $ ... $
    re.compile(r"\\\[(.+?)\\\]", re.DOTALL),          # \[ ... \]
    re.compile(r"\\\((.+?)\\\)", re.DOTALL),          # \( ... \)
    re.compile(r"\\begin\{equation\}(.+?)\\end\{equation\}", re.DOTALL),
    re.compile(r"\\begin\{align\}(.+?)\\end\{align\}", re.DOTALL),
    re.compile(r"\\begin\{eqnarray\}(.+?)\\end\{eqnarray\}", re.DOTALL),
]


def _find_latex_in_text(text: str) -> list[str]:
    """Find LaTeX equation fragments in text using regex patterns."""
    found: list[str] = []
    for pattern in _LATEX_PATTERNS:
        matches = pattern.findall(text)
        for m in matches:
            eq = m.strip()
            if eq and len(eq) > 3 and eq not in found:
                found.append(eq)
    return found


def normalize_equation(latex: str) -> str:
    """Normalize a LaTeX equation string.

    Strips unnecessary whitespace, standardizes delimiters, and applies
    basic formatting normalization.

    Args:
        latex: Raw LaTeX equation string.

    Returns:
        Normalized LaTeX string.
    """
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", latex).strip()

    # Remove redundant braces around single tokens
    normalized = re.sub(r"\{\s*([^{}<>|]+?)\s*\}", r"\1", normalized)

    return normalized
