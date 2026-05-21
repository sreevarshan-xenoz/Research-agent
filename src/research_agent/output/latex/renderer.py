from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

import jinja2


def escape_latex(value: str) -> str:
    """Escapes special LaTeX characters in a string."""
    if not value:
        return ""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    escaped = value
    # Handle backslash first to avoid escaping the escape sequences
    escaped = escaped.replace("\\", replacements["\\"])
    for original, replacement in replacements.items():
        if original == "\\":
            continue
        escaped = escaped.replace(original, replacement)
    return escaped


def _get_jinja_env() -> jinja2.Environment:
    template_dir = Path(__file__).resolve().parent / "templates"
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        autoescape=False,  # LaTeX is not HTML
        block_start_string='{%',
        block_end_string='%}',
        variable_start_string='{{',
        variable_end_string='}}',
        comment_start_string='{#',
        comment_end_string='#}',
    )


def render_main_tex(
    *,
    template_name: str,
    title: str,
    author_block: str,
    abstract: str,
    body: str,
    language: str = "en",
    acm_layout: str | None = None,
) -> str:
    """Renders the main.tex file using Jinja2 templates."""
    # Map friendly names to actual folder/file structure if needed
    # v2 uses ieee-1col, ieee-2col, acm, springer
    base_template = template_name
    if template_name.startswith("ieee"):
        base_template = "ieee"
    
    if acm_layout is None:
        try:
            from research_agent.config import load_settings
            acm_layout = load_settings().output.default_acm_layout
        except Exception:
            acm_layout = "sigconf"

    env = _get_jinja_env()
    try:
        template = env.get_template(f"{base_template}/main.tex.j2")
    except Exception as e:
        # Fallback to direct path for custom templates
        if "TemplateNotFound" in str(type(e)):
             raise FileNotFoundError(f"Template not found for: {template_name} (path: {base_template}/main.tex.j2)")
        raise e

    return template.render(
        title=escape_latex(title),
        author_block=escape_latex(author_block),
        abstract=escape_latex(abstract),
        body=body,
        columns=2 if "2col" in template_name else 1,
        language=language,
        acm_layout=acm_layout,
    )


def render_beamer_tex(
    *,
    topic: str,
    sections: list[dict[str, Any]],
) -> str:
    """Renders a Beamer presentation .tex file."""
    env = _get_jinja_env()
    try:
        template = env.get_template("beamer/main.tex.j2")
    except Exception:
        raise FileNotFoundError("Beamer template not found")

    return template.render(
        topic=escape_latex(topic),
        sections=[
            {
                "heading": escape_latex(s.get("heading", "Untitled")),
                "content": s.get("content", ""), # Body content often has latex, keep as is
            }
            for s in sections
        ],
    )


def build_bibtex(citations: Iterable[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for idx, citation in enumerate(citations, start=1):
        key = citation.get("key") or f"ref{idx}"
        title = citation.get("title") or "Untitled source"
        author = citation.get("author") or "Unknown"
        year = citation.get("year") or "2026"
        url = citation.get("url") or ""
        doi = citation.get("doi") or ""
        journal = citation.get("journal") or ""
        booktitle = citation.get("booktitle") or ""
        volume = citation.get("volume") or ""
        number = citation.get("number") or ""
        pages = citation.get("pages") or ""
        publisher = citation.get("publisher") or ""
        doc_type = citation.get("type") or ""

        # Preprints (arXiv) check
        is_preprint = False
        if doc_type and "arxiv" in str(doc_type).lower():
            is_preprint = True
        elif journal and "arxiv" in str(journal).lower():
            is_preprint = True
        elif publisher and "arxiv" in str(publisher).lower():
            is_preprint = True
        elif url and "arxiv.org" in str(url).lower():
            is_preprint = True
        elif citation.get("arxiv") or citation.get("arxiv_id"):
            is_preprint = True

        entry_type = "misc"
        if not is_preprint:
            if doc_type:
                dt_lower = str(doc_type).lower()
                if dt_lower in ("article", "journal-article", "journalarticle", "journal article"):
                    entry_type = "article"
                elif dt_lower in ("inproceedings", "proceedings-article", "proceedings", "conference-paper", "conferencepaper", "conference paper"):
                    entry_type = "inproceedings"
                elif dt_lower in ("book", "monograph"):
                    entry_type = "book"
                elif "thesis" in dt_lower or dt_lower in ("phdthesis", "mastersthesis"):
                    entry_type = "phdthesis"
                elif "report" in dt_lower or dt_lower in ("techreport", "technical-report"):
                    entry_type = "techreport"

            if entry_type == "misc":
                if journal:
                    entry_type = "article"
                elif booktitle:
                    entry_type = "inproceedings"
                elif publisher:
                    entry_type = "book"

        # Escape the textual fields
        escaped_title = escape_latex(str(title))
        escaped_author = escape_latex(str(author))
        escaped_journal = escape_latex(str(journal))
        escaped_booktitle = escape_latex(str(booktitle))
        escaped_publisher = escape_latex(str(publisher))

        block = [
            f"@{entry_type}{{{key},",
            f"  title = {{{escaped_title}}},",
            f"  author = {{{escaped_author}}},",
            f"  year = {{{year}}},",
        ]

        if entry_type == "article":
            if escaped_journal:
                block.append(f"  journal = {{{escaped_journal}}},")
            if volume:
                block.append(f"  volume = {{{volume}}},")
            if number:
                block.append(f"  number = {{{number}}},")
            if pages:
                block.append(f"  pages = {{{pages}}},")
        elif entry_type == "inproceedings":
            if escaped_booktitle:
                block.append(f"  booktitle = {{{escaped_booktitle}}},")
            if pages:
                block.append(f"  pages = {{{pages}}},")
            if publisher:
                block.append(f"  publisher = {{{escaped_publisher}}},")
        elif entry_type == "book":
            if escaped_publisher:
                block.append(f"  publisher = {{{escaped_publisher}}},")
            if volume:
                block.append(f"  volume = {{{volume}}},")
            if pages:
                block.append(f"  pages = {{{pages}}},")
        elif entry_type == "phdthesis":
            school = escaped_publisher or "Unknown University"
            block.append(f"  school = {{{school}}},")
        elif entry_type == "techreport":
            institution = escaped_publisher or "Unknown Institution"
            block.append(f"  institution = {{{institution}}},")
            if number:
                block.append(f"  number = {{{number}}},")

        if doi:
            block.append(f"  doi = {{{doi}}},")
        if url:
            # URLs in BibTeX \url should not be escaped by our general escape function
            # as \url handles special chars itself.
            block.append(f"  howpublished = {{\\url{{{url}}}}},")

        block.append("}")
        blocks.append("\n".join(block))

    if not blocks:
        return (
            "@misc{placeholder,\n"
            "  title = {No citation records available},\n"
            "  author = {Research Agent},\n"
            "  year = {2026}\n"
            "}\n"
        )
    return "\n\n".join(blocks) + "\n"


def build_compile_instructions(template_name: str) -> str:
    return (
        "# Compile Instructions\n\n"
        f"Template: {template_name}\n\n"
        "Run one of the following commands from this folder:\n\n"
        "- pdflatex main.tex\n"
        "- bibtex references\n"
        "- pdflatex main.tex\n"
        "- pdflatex main.tex\n\n"
        "Or upload main.tex and references.bib to Overleaf.\n"
    )


def validate_latex_package(
    *,
    template_name: str,
    main_tex: str,
    bibtex: str,
) -> list[str]:
    errors: list[str] = []
    normalized = main_tex.replace("\\\\", "\\")

    required_markers = [
        "\\begin{document}",
        "\\end{document}",
        "\\title",
        "\\author",
        "\\begin{abstract}",
        "\\bibliography{references}",
    ]
    for marker in required_markers:
        if marker not in normalized:
            errors.append(f"missing_latex_marker:{marker}")

    if "\\section{" not in normalized:
        errors.append("missing_required_section")

    if template_name.startswith("ieee") and "IEEEtran" not in normalized:
        errors.append("template_structure_invalid:ieee")
    if template_name.startswith("acm") and "acmart" not in normalized:
        errors.append("template_structure_invalid:acm")

    cite_keys: set[str] = set()
    for match in re.finditer(r"\\+cite\{([^}]+)\}", normalized):
        joined = match.group(1)
        for key in joined.split(","):
            stripped = key.strip()
            if stripped:
                cite_keys.add(stripped)

    bib_keys = {
        m.group(1).strip()
        for m in re.finditer(r"@\w+\{\s*([^,\s]+)", bibtex)
        if m.group(1).strip()
    }

    if cite_keys and not bib_keys:
        errors.append("missing_bib_entries")

    unresolved = sorted(cite_keys - bib_keys)
    if unresolved:
        errors.append("unresolved_citations:" + ",".join(unresolved))

    return errors
