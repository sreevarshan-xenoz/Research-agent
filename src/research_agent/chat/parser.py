from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_text_from_pdf(pdf_path: Path) -> dict[str, Any] | None:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        import fitz
        doc = fitz.open(pdf_path)
        text_parts: list[str] = []
        metadata: dict[str, Any] = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "pages": len(doc),
        }
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return {
            "text": "\n".join(text_parts),
            "metadata": metadata,
        }
    except Exception:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return {
                "text": text,
                "metadata": {"title": "", "author": "", "pages": len(pdf.pages)},
            }
    except ImportError:
        pass
    except Exception:
        return None
