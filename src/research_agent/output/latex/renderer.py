from __future__ import annotations

from pathlib import Path
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


def _template_path(template_name: str) -> Path:
    root = Path(__file__).resolve().parent / "templates" / template_name / "main.tex.j2"
    if not root.exists():
        raise FileNotFoundError(f"Template not found: {template_name}")
    return root


def render_main_tex(
    *,
    template_name: str,
    title: str,
    author_block: str,
    abstract: str,
    body: str,
) -> str:
    template = _template_path(template_name).read_text(encoding="utf-8")
    rendered = template
    rendered = rendered.replace("{{ title }}", escape_latex(title))
    rendered = rendered.replace("{{ author_block }}", escape_latex(author_block))
    rendered = rendered.replace("{{ abstract }}", escape_latex(abstract))
    rendered = rendered.replace("{{ body }}", body)
    return rendered


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
