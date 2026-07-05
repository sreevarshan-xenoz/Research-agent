"""
P27: Multi-Format Submission Pipeline — Style Compliance Checker

Validates LaTeX documents against conference/journal formatting guidelines:
- Page limit enforcement
- Required sections check
- Citation/Bibliography compliance
- Figure/Table limits
- Font and margin requirements
- Language and length checks
"""

from __future__ import annotations

import re
from typing import Any

from research_agent.output.format_converter import get_format_info


# ── Conference-Specific Rules ────────────────────────────────

CONFERENCE_RULES: dict[str, dict[str, Any]] = {
    "ieee": {
        "max_pages": 6,
        "min_pages": 4,
        "max_references": 30,
        "max_figures": 10,
        "max_tables": 5,
        "required_sections": ["abstract", "introduction", "conclusion"],
        "recommended_sections": ["methodology", "results", "discussion"],
        "forbidden_packages": ["hyperref", "color", "geometry"],
        "allowed_font_sizes": [10],
        "double_column": True,
        "line_spacing": 1.0,
        "abstract_max_words": 250,
        "title_max_chars": 100,
    },
    "acm": {
        "max_pages": 10,
        "min_pages": 4,
        "max_references": 50,
        "max_figures": 15,
        "max_tables": 8,
        "required_sections": ["abstract", "introduction", "conclusion", "references"],
        "recommended_sections": ["methodology", "results", "discussion", "acknowledgments"],
        "forbidden_packages": [],
        "allowed_font_sizes": [10],
        "double_column": True,
        "line_spacing": 1.0,
        "abstract_max_words": 300,
        "title_max_chars": 150,
        "requires_ccs_concepts": True,
        "requires_keywords": True,
    },
    "springer": {
        "max_pages": 12,
        "min_pages": 6,
        "max_references": 40,
        "max_figures": 15,
        "max_tables": 8,
        "required_sections": ["abstract", "introduction", "conclusion", "references"],
        "recommended_sections": ["methodology", "results", "discussion"],
        "forbidden_packages": [],
        "allowed_font_sizes": [10],
        "double_column": False,
        "line_spacing": 1.0,
        "abstract_max_words": 200,
        "title_max_chars": 120,
    },
    "elsevier": {
        "max_pages": 8,
        "min_pages": 4,
        "max_references": 35,
        "max_figures": 8,
        "max_tables": 6,
        "required_sections": ["abstract", "introduction", "conclusion", "references"],
        "recommended_sections": ["methodology", "results", "discussion", "acknowledgments"],
        "forbidden_packages": [],
        "allowed_font_sizes": [10, 11, 12],
        "double_column": True,
        "line_spacing": 1.5,
        "abstract_max_words": 300,
        "title_max_chars": 120,
    },
}


def get_rules(format_name: str) -> dict[str, Any]:
    """Get style rules for a conference format."""
    fmt = format_name.lower().strip()
    if fmt in CONFERENCE_RULES:
        return CONFERENCE_RULES[fmt]
    return CONFERENCE_RULES.get("ieee", {})


# ── Validation Functions ─────────────────────────────────────

def check_style(
    tex: str,
    format_name: str,
    *,
    bibtex: str | None = None,
) -> dict[str, Any]:
    """Run comprehensive style compliance check on a LaTeX document.

    Args:
        tex: The LaTeX document content.
        format_name: Target format (ieee, acm, springer, elsevier).
        bibtex: Optional BibTeX content for citation checks.

    Returns:
        Dict with 'passed', 'issues', 'summary', and 'score'.
    """
    rules = get_rules(format_name)
    issues: list[dict[str, Any]] = []

    # 1. Required sections check
    _check_required_sections(tex, rules, issues)

    # 2. Page length estimation
    _check_page_length(tex, rules, issues)

    # 3. Reference count
    _check_references(tex, rules, issues, bibtex)

    # 4. Figure count
    _check_figures(tex, rules, issues)

    # 5. Table count
    _check_tables(tex, rules, issues)

    # 6. Forbidden packages
    _check_forbidden_packages(tex, rules, issues)

    # 7. Abstract word count
    _check_abstract(tex, rules, issues)

    # 8. Title length
    _check_title(tex, rules, issues)

    # 9. Format-specific checks
    _check_format_specific(tex, format_name, rules, issues)

    # 10. Check for common LaTeX errors
    _check_latex_errors(tex, issues)

    # Calculate score
    total_checks = len(issues) + 1  # +1 for the base pass
    passed = sum(1 for i in issues if i.get("severity") != "error")
    errors = sum(1 for i in issues if i.get("severity") == "error")
    score = max(0.0, 1.0 - (errors / max(total_checks, 1)))

    return {
        "format": format_name,
        "format_name": get_format_info(format_name)["name"],
        "score": round(score, 2),
        "passed": errors == 0,
        "total_issues": len(issues),
        "errors": errors,
        "warnings": sum(1 for i in issues if i.get("severity") == "warning"),
        "info": sum(1 for i in issues if i.get("severity") == "info"),
        "issues": issues,
        "summary": {
            "max_pages": rules.get("max_pages"),
            "required_sections": rules.get("required_sections"),
            "max_references": rules.get("max_references"),
            "max_figures": rules.get("max_figures"),
        },
    }


def _check_required_sections(tex: str, rules: dict, issues: list) -> None:
    """Check that required sections are present."""
    tex_lower = tex.lower()
    for section in rules.get("required_sections", []):
        section_variants = [
            f"\\section{{{section}}}",
            f"\\section*{{{section}}}",
            f"\\section{{ {section} }}",
        ]
        found = any(variant in tex_lower for variant in section_variants)
        if not found:
            # Try flexible matching
            found = bool(re.search(
                r"\\section\{?[^}]*" + re.escape(section) + r"[^}]*\}?",
                tex_lower,
            ))

        if not found:
            issues.append({
                "type": "missing_section",
                "severity": "error",
                "message": f"Missing required section: '{section}'",
                "detail": f"The {section} section is required for this format",
            })


def _check_page_length(tex: str, rules: dict, issues: list) -> None:
    """Estimate page count and check against limits."""
    # Rough estimation: ~3000 chars per page for 2-column, ~2500 for 1-column
    chars_per_page = 2500 if rules.get("double_column") else 3000
    # Strip preamble and bibliography for content estimate
    body_match = re.search(
        r"\\begin\{document\}(.*?)\\end\{document\}",
        tex,
        re.DOTALL,
    )
    body = body_match.group(1) if body_match else tex
    body = re.sub(r"\\bibliography[^}]*\}[^}]*\}", "", body)

    estimated_pages = max(1, len(body) // chars_per_page)
    max_pages = rules.get("max_pages", 10)

    if estimated_pages > max_pages:
        issues.append({
            "type": "page_limit",
            "severity": "error",
            "message": f"Estimated {estimated_pages} pages exceeds {max_pages} page limit",
            "detail": f"Content length: {len(body)} chars (est. {estimated_pages} pages). Max: {max_pages} pages.",
            "estimated_pages": estimated_pages,
            "max_pages": max_pages,
        })
    elif estimated_pages > max_pages * 0.85:
        issues.append({
            "type": "page_limit_warning",
            "severity": "warning",
            "message": f"Estimated {estimated_pages} pages is close to {max_pages} page limit",
            "detail": "Consider trimming content to stay within limits",
            "estimated_pages": estimated_pages,
            "max_pages": max_pages,
        })

    min_pages = rules.get("min_pages", 0)
    if estimated_pages < min_pages:
        issues.append({
            "type": "page_minimum",
            "severity": "warning",
            "message": f"Estimated {estimated_pages} pages is below {min_pages} page minimum",
            "detail": "Consider expanding content to meet minimum length",
        })


def _check_references(tex: str, rules: dict, issues: list, bibtex: str | None) -> None:
    """Check reference count and citation health."""
    cite_count = len(re.findall(r"\\cite\{[^}]*\}", tex))
    ref_count = 0
    if bibtex:
        ref_count = len(re.findall(r"@\w+\{", bibtex))

    max_refs = rules.get("max_references", 50)
    if ref_count > max_refs:
        issues.append({
            "type": "reference_limit",
            "severity": "warning",
            "message": f"{ref_count} references exceeds {max_refs} recommended limit",
            "detail": f"Found {ref_count} bib entries. Recommended: <= {max_refs}",
        })

    if cite_count == 0:
        issues.append({
            "type": "no_citations",
            "severity": "error",
            "message": "No citations found in the document",
            "detail": "Research papers should cite relevant prior work",
        })

    if bibtex and ref_count == 0:
        issues.append({
            "type": "missing_bibliography",
            "severity": "error",
            "message": "No bibliography entries found",
            "detail": "The .bib file appears to be empty",
        })

    unresolved = _find_unresolved_citations(tex, bibtex)
    if unresolved:
        issues.append({
            "type": "unresolved_citations",
            "severity": "warning",
            "message": f"{len(unresolved)} unresolved citations: {', '.join(unresolved[:5])}",
            "detail": f"Citations without matching bib entries: {', '.join(unresolved)}",
        })


def _find_unresolved_citations(tex: str, bibtex: str | None) -> list[str]:
    """Find citations that don't have matching bib entries."""
    if not bibtex:
        return []

    cited = set()
    for match in re.finditer(r"\\cite\{([^}]*)\}", tex):
        for key in match.group(1).split(","):
            cited.add(key.strip())

    bib_keys = set()
    for match in re.finditer(r"@\w+\{\s*([^,\s]+)", bibtex):
        bib_keys.add(match.group(1).strip())

    return sorted(cited - bib_keys)


def _check_figures(tex: str, rules: dict, issues: list) -> None:
    """Check figure count against limits."""
    fig_count = len(re.findall(r"\\begin\{figure\}", tex))
    fig_count += len(re.findall(r"\\begin\{figure\*\}", tex))
    max_figs = rules.get("max_figures", 15)

    if fig_count > max_figs:
        issues.append({
            "type": "figure_limit",
            "severity": "warning",
            "message": f"{fig_count} figures exceeds {max_figs} recommended limit",
            "detail": f"Found {fig_count} figures. Recommended: <= {max_figs}",
        })


def _check_tables(tex: str, rules: dict, issues: list) -> None:
    """Check table count against limits."""
    tbl_count = len(re.findall(r"\\begin\{table\}", tex))
    max_tbls = rules.get("max_tables", 8)

    if tbl_count > max_tbls:
        issues.append({
            "type": "table_limit",
            "severity": "info",
            "message": f"{tbl_count} tables exceeds {max_tbls} recommended limit",
        })


def _check_forbidden_packages(tex: str, rules: dict, issues: list) -> None:
    """Check for forbidden LaTeX packages."""
    for pkg in rules.get("forbidden_packages", []):
        pattern = rf"\\usepackage[^}}]*{{{re.escape(pkg)}}}"
        if re.search(pattern, tex):
            issues.append({
                "type": "forbidden_package",
                "severity": "error",
                "message": f"Forbidden package: '{pkg}'",
                "detail": f"Package '{pkg}' is not allowed in this format",
            })


def _check_abstract(tex: str, rules: dict, issues: list) -> None:
    """Check abstract word count."""
    abstract_match = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
        tex,
        re.DOTALL,
    )
    if abstract_match:
        words = len(abstract_match.group(1).split())
        max_words = rules.get("abstract_max_words", 250)
        if words > max_words:
            issues.append({
                "type": "abstract_length",
                "severity": "warning",
                "message": f"Abstract is {words} words (max {max_words})",
                "detail": f"Abstract word count: {words}/{max_words}",
            })
    else:
        issues.append({
            "type": "missing_abstract",
            "severity": "error",
            "message": "No abstract found",
            "detail": "An abstract is required for this format",
        })


def _check_title(tex: str, rules: dict, issues: list) -> None:
    """Check title length."""
    title_match = re.search(r"\\title\{([^}]*)\}", tex)
    if title_match:
        title = title_match.group(1)
        max_chars = rules.get("title_max_chars", 100)
        if len(title) > max_chars:
            issues.append({
                "type": "title_length",
                "severity": "warning",
                "message": f"Title is {len(title)} chars (max {max_chars})",
                "detail": f"Title length: {len(title)}/{max_chars}",
            })


def _check_format_specific(tex: str, format_name: str, rules: dict, issues: list) -> None:
    """Run format-specific checks."""
    if format_name == "acm":
        if rules.get("requires_ccs_concepts"):
            if "\\ccsdesc" not in tex:
                issues.append({
                    "type": "missing_ccs_concepts",
                    "severity": "warning",
                    "message": "ACM requires CCS Concepts (\\ccsdesc)",
                    "detail": "Add \\ccsdesc[500] concepts for ACM submission",
                })
        if rules.get("requires_keywords"):
            if "\\keywords" not in tex:
                issues.append({
                    "type": "missing_keywords",
                    "severity": "info",
                    "message": "Consider adding \\keywords for ACM submission",
                })

    if format_name == "ieee":
        if "\\pubid" not in tex:
            issues.append({
                "type": "missing_pubid",
                "severity": "info",
                "message": "Consider adding \\pubid for IEEE publication ID",
            })


def _check_latex_errors(tex: str, issues: list) -> None:
    """Check for common LaTeX errors."""
    # Unmatched braces
    open_braces = tex.count("{")
    close_braces = tex.count("}")
    if open_braces != close_braces:
        issues.append({
            "type": "unmatched_braces",
            "severity": "error",
            "message": f"Unmatched braces: {open_braces} open vs {close_braces} closed",
        })

    # Unclosed environments
    envs_opened = re.findall(r"\\begin\{(\w+)\}", tex)
    envs_closed = re.findall(r"\\end\{(\w+)\}", tex)
    from collections import Counter
    open_counts = Counter(envs_opened)
    close_counts = Counter(envs_closed)
    for env, count in open_counts.items():
        diff = count - close_counts.get(env, 0)
        if diff > 0:
            issues.append({
                "type": "unclosed_environment",
                "severity": "error",
                "message": f"Unclosed environment: '{env}' ({diff} unclosed)",
            })

    # Check for common Unicode in LaTeX (should be escaped)
    unicode_chars = re.findall(r"[^\x00-\x7F]", tex)
    if unicode_chars:
        unique = set(unicode_chars)
        if len(unique) > 10:
            issues.append({
                "type": "unicode_characters",
                "severity": "warning",
                "message": f"Found {len(unique)} unique non-ASCII characters",
                "detail": "Non-ASCII characters may not render correctly in LaTeX",
            })
