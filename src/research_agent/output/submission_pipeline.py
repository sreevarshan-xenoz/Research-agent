"""
P27: Multi-Format Submission Pipeline — One-Click Export

Provides unified export to:
- Overleaf (snip URL, form HTML, Git push)
- arXiv (ZIP archive with proper arXiv structure)
- Conference submission (ZIP with format-appropriate structure)
- Direct format conversion + style check
"""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from research_agent.output.format_converter import (
    convert_latex_format,
    convert_to_all_formats,
    list_formats,
)
from research_agent.output.style_checker import check_style
from research_agent.output.content_adapter import adapt_content
from research_agent.output.overleaf import (
    build_overleaf_import_url,
    build_overleaf_form_html,
    git_push_to_overleaf,
    check_overleaf_config,
)

logger = logging.getLogger(__name__)


async def run_submission_pipeline(
    tex: str,
    *,
    format_name: str = "ieee",
    bibtex: str | None = None,
    topic: str | None = None,
    run_id: str | None = None,
    check_only: bool = False,
) -> dict[str, Any]:
    """Run the full submission pipeline: check → convert → adapt → export.

    Args:
        tex: The LaTeX content to process.
        format_name: Target format (ieee, acm, springer, elsevier).
        bibtex: Optional BibTeX content.
        topic: Optional research topic.
        run_id: Optional run ID for artifact lookup.
        check_only: If True, only run style check (no conversion/adaptation).

    Returns:
        Dict with pipeline results including style check, conversion, and export options.
    """
    results: dict[str, Any] = {
        "format": format_name,
        "format_name": _format_display_name(format_name),
        "style_check": None,
        "conversion_needed": False,
        "conversion": None,
        "adaptation_needed": False,
        "adaptation": None,
        "export_options": {},
    }

    # 1. Style compliance check
    style_result = check_style(tex, format_name, bibtex=bibtex)
    results["style_check"] = style_result

    if check_only:
        return results

    # 2. Format detection and conversion
    detected_format = _detect_format(tex)
    if detected_format and detected_format != format_name:
        results["conversion_needed"] = True
        conversion_result = await convert_latex_format(
            tex, format_name, bibtex=bibtex, topic=topic,
        )
        results["conversion"] = conversion_result
        working_tex = conversion_result.get("tex", tex)
    else:
        working_tex = tex

    # 3. Content adaptation (if needed)
    adapt_result = await adapt_content(
        working_tex, format_name, bibtex=bibtex,
    )
    results["adaptation"] = adapt_result
    results["adaptation_needed"] = adapt_result.get("adapted", False)

    if adapt_result.get("adapted"):
        final_tex = adapt_result.get("tex", working_tex)
    else:
        final_tex = working_tex

    # 4. Generate export options
    results["export_options"] = _generate_export_options(
        final_tex, format_name, bibtex=bibtex, topic=topic, run_id=run_id,
    )

    # 5. Overall status
    style_errors = len(style_result.get("issues", []))
    results["ready_for_submission"] = style_result.get("passed", False)
    results["issues_remaining"] = style_errors

    return results


def _detect_format(tex: str) -> str | None:
    """Detect the current LaTeX document format from document class."""
    docclass_match = __import__("re").search(
        r"\\documentclass(?:\[[^\]]*\])?\{(IEEEtran|acmart|llncs|elsarticle|svjour3|article)\}",
        tex,
    )
    if not docclass_match:
        return None

    cls = docclass_match.group(1).lower()
    mapping = {
        "ieeetran": "ieee",
        "acmart": "acm",
        "llncs": "springer",
        "svjour3": "springer",
        "elsarticle": "elsevier",
    }
    return mapping.get(cls)


def _format_display_name(fmt: str) -> str:
    """Get display name for a format."""
    names = {
        "ieee": "IEEE",
        "acm": "ACM",
        "springer": "Springer",
        "elsevier": "Elsevier",
    }
    return names.get(fmt, fmt.upper())


def _generate_export_options(
    tex: str,
    format_name: str,
    *,
    bibtex: str | None = None,
    topic: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Generate one-click export options."""
    options = {}
    topic = topic or "Research Paper"

    # Overleaf
    clean_bib = bibtex or _generate_placeholder_bib()
    options["overleaf"] = {
        "label": "Push to Overleaf",
        "snip_url": build_overleaf_import_url(tex, clean_bib, project_name=topic),
        "form_html": build_overleaf_form_html(tex, clean_bib, project_name=topic),
    }

    # arXiv ZIP
    options["arxiv"] = {
        "label": "Download arXiv ZIP",
        "filename": _arxiv_filename(topic, format_name),
        "files": _build_arxiv_archive(tex, format_name, bibtex=clean_bib, topic=topic),
    }

    # Conference submission ZIP
    options["conference"] = {
        "label": "Download Conference ZIP",
        "filename": _conference_filename(topic, format_name),
        "files": _build_conference_archive(tex, format_name, bibtex=clean_bib, topic=topic),
    }

    # Direct LaTeX download
    options["latex"] = {
        "label": "Download LaTeX (.tex)",
        "filename": f"{_slugify(topic)}-{format_name}.tex",
    }

    return options


def _build_arxiv_archive(
    tex: str,
    format_name: str,
    *,
    bibtex: str | None = None,
    topic: str | None = None,
) -> dict[str, str]:
    """Build arXiv-compatible submission files.

    arXiv requires:
    - main.tex (or paper.tex)
    - references.bib
    - Figures in a separate directory
    - A .bbl file (optional but recommended)
    """
    files: dict[str, str] = {}

    # Main tex file
    files["main.tex"] = tex

    # References
    if bibtex:
        files["references.bib"] = bibtex

    # Generate compile script
    compile_script = _generate_compile_script(format_name)
    files["compile.sh"] = compile_script

    # arXiv metadata
    arxiv_meta = _generate_arxiv_meta(topic or "Research Paper")
    files["arXiv_meta.tex"] = arxiv_meta

    return files


def _build_conference_archive(
    tex: str,
    format_name: str,
    *,
    bibtex: str | None = None,
    topic: str | None = None,
) -> dict[str, str]:
    """Build conference submission archive with proper structure."""
    files: dict[str, str] = {}

    # Rename to paper.tex for anonymity
    files["paper.tex"] = tex

    if bibtex:
        files["references.bib"] = bibtex

    # Submission info
    info = {
        "format": format_name,
        "topic": topic or "Research Paper",
        "generated": datetime.now().isoformat(),
        "files": ["paper.tex", "references.bib"],
    }
    files["submission_info.json"] = json.dumps(info, indent=2)

    return files


def _arxiv_filename(topic: str, format_name: str) -> str:
    """Generate arXiv-compatible filename."""
    slug = _slugify(topic)
    return f"{slug}-arxiv-{format_name}.zip"


def _conference_filename(topic: str, format_name: str) -> str:
    """Generate conference submission filename."""
    slug = _slugify(topic)
    return f"{slug}-{format_name}-submission.zip"


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    import re
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug[:60] or "paper"


def _generate_compile_script(format_name: str) -> str:
    """Generate a shell script for compiling the LaTeX."""
    return (
        "#!/bin/bash\n"
        "# Compile script for arXiv submission\n"
        "pdflatex main.tex\n"
        "bibtex main\n"
        "pdflatex main.tex\n"
        "pdflatex main.tex\n"
    )


def _generate_arxiv_meta(topic: str) -> str:
    """Generate arXiv metadata LaTeX include."""
    return (
        "% arXiv metadata\n"
        "% This file contains metadata for arXiv submission.\n"
        f"% Title: {topic}\n"
        f"% Generated: {datetime.now().isoformat()}\n"
    )


def _generate_placeholder_bib() -> str:
    """Generate a placeholder bibtex if none provided."""
    return (
        "@misc{placeholder,\n"
        "  title = {Generated Research Paper},\n"
        "  author = {Research Agent},\n"
        "  year = {2026},\n"
        "}\n"
    )


# ── ZIP Archive Generation ───────────────────────────────────

def create_export_zip(
    files: dict[str, str],
    *,
    archive_name: str = "export.zip",
) -> tuple[bytes, str]:
    """Create a ZIP archive from generated files.

    Args:
        files: Dict of {filename: content} pairs.
        archive_name: Name for the ZIP file.

    Returns:
        Tuple of (zip_bytes, archive_name).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)

    return buf.getvalue(), archive_name


async def convert_and_export(
    tex: str,
    target_format: str,
    *,
    bibtex: str | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    """Convert format and return all export options.

    One-stop function for the full pipeline.
    """
    return await run_submission_pipeline(
        tex,
        format_name=target_format,
        bibtex=bibtex,
        topic=topic,
    )
