from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable


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


def _get_jinja_env() -> "jinja2.Environment":
    import jinja2
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
) -> str:
    """Renders the main.tex file using Jinja2 templates."""
    # Map friendly names to actual folder/file structure if needed
    # v2 uses ieee-1col, ieee-2col, acm, springer
    base_template = template_name
    if template_name.startswith("ieee"):
        base_template = "ieee"
    
    env = _get_jinja_env()
    try:
        template = env.get_template(f"{base_template}/main.tex.j2")
    except Exception:
        # Fallback to direct path for custom templates
        raise FileNotFoundError(f"Template not found for: {template_name}")

    return template.render(
        title=escape_latex(title),
        author_block=escape_latex(author_block),
        abstract=escape_latex(abstract),
        body=body,
        columns=2 if "2col" in template_name else 1
    )


def build_bibtex(citations: Iterable[dict[str, str]]) -> str:
    blocks: list[str] = []
    for idx, citation in enumerate(citations, start=1):
        key = citation.get("key") or f"ref{idx}"
        title = escape_latex(citation.get("title", "Untitled source"))
        author = escape_latex(citation.get("author", "Unknown"))
        year = citation.get("year", "2026")
        url = citation.get("url", "")

        block = [
            f"@misc{{{key},",
            f"  title = {{{title}}},",
            f"  author = {{{author}}},",
            f"  year = {{{year}}},",
        ]
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
