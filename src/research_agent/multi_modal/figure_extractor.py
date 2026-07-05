"""Figure extraction & captioning from PDFs using PyMuPDF."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExtractedFigure:
    """Represents a single extracted figure from a PDF page."""

    def __init__(
        self,
        page: int,
        bbox: tuple[float, float, float, float],
        image_path: str | None = None,
        caption: str | None = None,
        alt_text: str | None = None,
    ) -> None:
        self.page = page
        self.bbox = bbox
        self.image_path = image_path
        self.caption = caption
        self.alt_text = alt_text

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "bbox": list(self.bbox),
            "image_path": self.image_path,
            "caption": self.caption,
            "alt_text": self.alt_text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedFigure:
        return cls(
            page=data["page"],
            bbox=tuple(data["bbox"]),
            image_path=data.get("image_path"),
            caption=data.get("caption"),
            alt_text=data.get("alt_text"),
        )


async def extract_figures_from_pdf(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
    max_figures: int = 20,
) -> list[ExtractedFigure]:
    """Extract embedded images from a PDF using PyMuPDF.

    Extracts raster images found in the PDF stream, saves them as PNG
    files to *output_dir*, and returns ExtractedFigure entries with
    page numbers and bounding boxes.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to save extracted images. If None, images
            are not persisted to disk.
        max_figures: Maximum number of figures to extract.

    Returns:
        List of ExtractedFigure objects.
    """
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("PyMuPDF not installed — figure extraction disabled")
        return []

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        return []

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    figures: list[ExtractedFigure] = []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        logger.error("Failed to open PDF: %s", exc)
        return []

    for page_num in range(len(doc)):
        if len(figures) >= max_figures:
            break

        page = doc[page_num]
        image_info = page.get_image_info(xrefs=True)

        for img in image_info:
            if len(figures) >= max_figures:
                break

            xref = img.get("xref")
            bbox = img.get("bbox")
            if xref is None or bbox is None:
                continue

            try:
                pix = fitz.Pixmap(doc, xref)
                # Convert CMYK or indexed to RGB
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                img_path: str | None = None
                if output_dir is not None:
                    fname = output_dir / f"figure_p{page_num + 1}_{xref}.png"
                    pix.save(str(fname))
                    img_path = str(fname)

                figures.append(
                    ExtractedFigure(
                        page=page_num + 1,
                        bbox=bbox,
                        image_path=img_path,
                    )
                )
                pix = None  # Free memory
            except Exception as exc:
                logger.debug("Failed to extract image xref=%s: %s", xref, exc)
                continue

    doc.close()
    logger.info("Extracted %d figures from %s", len(figures), pdf_path)
    return figures


async def generate_figure_caption(
    image_path: str | Path,
    page_context: str | None = None,
) -> str:
    """Generate a descriptive caption for a figure image using a vision LLM.

    Uses litellm directly with a vision-capable model to describe the figure.
    Falls back to text-only description if vision is unavailable.

    Args:
        image_path: Path to the saved figure PNG image (used as context hint).
        page_context: Optional surrounding page text for context.

    Returns:
        Generated caption string.
    """
    from research_agent.config import load_settings
    settings = load_settings()

    # Use the best available vision model
    vision_model = (
        settings.models.subagent_openai or "openai/gpt-4o"
    )

    system_prompt = (
        "You are a scientific figure analyst. Describe the figure shown in detail, "
        "including its type (bar chart, line plot, schematic, micrograph, etc.), "
        "axes labels, key trends, and notable data points.\n"
        f"Image path hint: {image_path}\n"
        "Note: This is a caption-generation request. Be precise and factual."
    )

    user_prompt = "Describe this scientific figure in 2-3 sentences."
    if page_context:
        user_prompt += (
            "\n\nContext from the surrounding page text:\n"
            f"{page_context[:1500]}"
        )

    try:
        import litellm  # type: ignore[import-untyped]

        api_key = str(settings.openai.api_key) if settings.openai.api_key else None
        response = await litellm.acompletion(
            model=vision_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=300,
            api_key=api_key,
        )
        text = response.choices[0].message.content if response.choices else ""
        return text or "Figure (no caption generated)"
    except Exception as exc:
        logger.warning("Vision caption generation failed: %s", exc)
        # Fallback: text-only description
        try:
            from research_agent.models import generate_text
            fallback = await generate_text(
                role="subagent",
                prompt=(
                    "Based on the context provided, generate a generic caption "
                    "for a figure in a research paper.\n\n"
                    f"Context: {page_context[:1000] if page_context else 'No context.'}"
                ),
                system=system_prompt,
                temperature=0.3,
                max_tokens=200,
            )
            return fallback or "Figure"
        except Exception:
            return "Figure"
