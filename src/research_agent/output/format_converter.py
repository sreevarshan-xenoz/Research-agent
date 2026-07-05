"""
P27: Multi-Format Submission Pipeline — Format Converter

Converts LaTeX documents between different conference/journal formats:
- IEEE (IEEEtran)
- ACM (acmart)
- Springer (llncs or svjour3)
- Elsevier (elsarticle)

Uses LLM-based conversion to handle the structural differences between
document classes while preserving content, citations, and formatting.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from research_agent.models import agenerate_json
from research_agent.output.latex.renderer import render_main_tex, build_bibtex

logger = logging.getLogger(__name__)

# ── Supported Formats ────────────────────────────────────────

FORMATS = {
    "ieee": {
        "name": "IEEE",
        "documentclass": "IEEEtran",
        "class_options": "[conference,twocolumn]",
        "bibstyle": "IEEEtran",
        "sections_required": ["abstract", "introduction", "conclusion"],
        "max_pages": 6,
        "max_references": 30,
        "description": "IEEE Conference (2-column)",
    },
    "acm": {
        "name": "ACM",
        "documentclass": "acmart",
        "class_options": "[sigconf]",
        "bibstyle": "ACM-Reference-Format",
        "sections_required": ["abstract", "introduction", "conclusion"],
        "max_pages": 10,
        "max_references": 50,
        "description": "ACM Conference (sigconf)",
    },
    "springer": {
        "name": "Springer",
        "documentclass": "llncs",
        "class_options": "",
        "bibstyle": "splncs04",
        "sections_required": ["abstract", "introduction", "conclusion"],
        "max_pages": 12,
        "max_references": 40,
        "description": "Springer LNCS",
    },
    "elsevier": {
        "name": "Elsevier",
        "documentclass": "elsarticle",
        "class_options": "[5p]",
        "bibstyle": "elsarticle-num",
        "sections_required": ["abstract", "introduction", "conclusion"],
        "max_pages": 8,
        "max_references": 35,
        "description": "Elsevier Journal (5p)",
    },
}

# ── Format Metadata ──────────────────────────────────────────

def get_format_info(fmt: str) -> dict[str, Any]:
    """Get metadata about a supported format."""
    fmt = fmt.lower().strip()
    if fmt not in FORMATS:
        raise ValueError(f"Unsupported format: {fmt}. Supported: {', '.join(FORMATS.keys())}")
    return FORMATS[fmt]


def list_formats() -> list[dict[str, str]]:
    """List all supported export formats."""
    return [
        {"id": fid, "name": info["name"], "description": info["description"]}
        for fid, info in FORMATS.items()
    ]


# ── LLM-Based Format Conversion ──────────────────────────────

async def convert_latex_format(
    source_tex: str,
    target_format: str,
    *,
    title: str | None = None,
    bibtex: str | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    """Convert LaTeX between formats using LLM.

    Args:
        source_tex: The source LaTeX content.
        target_format: Target format (ieee, acm, springer, elsevier).
        title: Optional override title.
        bibtex: Optional BibTeX content to include.
        topic: Optional research topic context.

    Returns:
        Dict with 'tex' (converted LaTeX), 'warnings', and 'changes_made'.
    """
    target_info = get_format_info(target_format)
    fmt_name = target_info["name"]

    prompt = (
        f"You are a LaTeX format conversion expert. Convert the following research paper "
        f"from its current format to {fmt_name} format ({target_info['documentclass']}).\n\n"
        f"Target format requirements:\n"
        f"- Document class: {target_info['documentclass']} {target_info['class_options']}\n"
        f"- Bibliography style: {target_info['bibstyle']}\n"
        f"- Max pages: {target_info['max_pages']}\n"
        f"- Required sections: {', '.join(target_info['sections_required'])}\n\n"
        f"Conversion rules:\n"
        f"1. Change \\documentclass to {target_info['documentclass']} {target_info['class_options']}\n"
        f"2. Add the appropriate packages for {fmt_name} format\n"
        f"3. Convert \\bibliographystyle to {target_info['bibstyle']}\n"
        f"4. Preserve ALL content, citations, figures, and tables\n"
        f"5. Adapt section headings format if needed\n"
        f"6. Ensure proper abstract environment\n"
        f"7. Remove format-specific packages that are incompatible\n\n"
        f"Source LaTeX:\n```\n{source_tex}\n```\n\n"
        f"Output a JSON object with keys:\n"
        f"- 'tex': The complete converted LaTeX document\n"
        f"- 'warnings': Array of any warnings about conversion issues\n"
        f"- 'changes_made': Array describing significant changes made\n"
        f"- 'estimated_pages': Estimated page count in target format"
    )

    try:
        result = await agenerate_json(
            role="orchestrator",
            prompt=prompt,
            temperature=0.1,
            max_tokens=8192,
        )

        if not result or not isinstance(result, dict):
            raise ValueError("LLM returned invalid conversion result")

        tex = result.get("tex", source_tex)
        warnings = result.get("warnings", [])
        changes = result.get("changes_made", [])
        estimated_pages = result.get("estimated_pages", 0)

        # Add bibtex if provided
        if bibtex and "\\bibliography{references}" in tex:
            pass  # Keep the bibliography reference

        return {
            "tex": tex,
            "format": target_format,
            "format_name": fmt_name,
            "warnings": warnings,
            "changes_made": changes,
            "estimated_pages": estimated_pages,
        }

    except Exception as exc:
        logger.warning("LLM format conversion failed: %s", exc)
        # Fallback: simple template swap
        fallback = _fallback_convert(source_tex, target_format)
        return {
            "tex": fallback,
            "format": target_format,
            "format_name": fmt_name,
            "warnings": [f"LLM conversion failed, used fallback: {exc}"],
            "changes_made": ["Applied template structure"],
            "estimated_pages": 0,
        }


def _fallback_convert(source_tex: str, target_format: str) -> str:
    """Simple fallback conversion that swaps document class and bibstyle."""
    target_info = get_format_info(target_format)

    tex = source_tex
    # Replace documentclass
    tex = re.sub(
        r"\\documentclass[^}]*(?:{[^}]*})?",
        f"\\documentclass{target_info['class_options']}{{{target_info['documentclass']}}}",
        tex,
    )
    # Replace bibstyle
    tex = re.sub(
        r"\\bibliographystyle{[^}]*}",
        f"\\bibliographystyle{{{target_info['bibstyle']}}}",
        tex,
    )
    # Remove format-specific packages
    format_packages = [
        r"\\usepackage[^}]*\{IEEEtran\}", r"\\usepackage[^}]*\{acmart\}",
        r"\\usepackage[^}]*\{llncs\}", r"\\usepackage[^}]*\{elsarticle\}",
    ]
    for pattern in format_packages:
        tex = re.sub(pattern, f"% {pattern} - removed for {target_format}", tex)

    return tex


# ── Batch Conversion ─────────────────────────────────────────

async def convert_to_all_formats(
    source_tex: str,
    *,
    bibtex: str | None = None,
    topic: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Convert a LaTeX document to all supported formats."""
    results = {}
    for fmt in FORMATS:
        try:
            result = await convert_latex_format(
                source_tex,
                fmt,
                bibtex=bibtex,
                topic=topic,
            )
            results[fmt] = result
        except Exception as exc:
            logger.error("Failed to convert to %s: %s", fmt, exc)
            results[fmt] = {
                "error": str(exc),
                "format": fmt,
                "format_name": FORMATS[fmt]["name"],
            }
    return results
