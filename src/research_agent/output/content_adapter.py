"""
P27: Multi-Format Submission Pipeline — Content Adapter

Automatically adapts LaTeX content to match template constraints:
- Trims/summarizes content to fit page limits
- Adjusts figure/table placement
- Manages bibliography size
- Adapts to single/double column layout
"""

from __future__ import annotations

import logging
import re
from typing import Any

from research_agent.models import agenerate_json
from research_agent.output.style_checker import check_style, get_rules
from research_agent.output.latex.renderer import render_main_tex

logger = logging.getLogger(__name__)


async def adapt_content(
    tex: str,
    format_name: str,
    *,
    bibtex: str | None = None,
    target_pages: int | None = None,
    preserve_sections: list[str] | None = None,
) -> dict[str, Any]:
    """Auto-adapt LaTeX content to match template constraints.

    Uses LLM to condense or expand content to fit page limits while
    preserving the key contributions and structure.

    Args:
        tex: The LaTeX document to adapt.
        format_name: Target format (ieee, acm, springer, elsevier).
        bibtex: Optional BibTeX content.
        target_pages: Target page count (defaults to format's max).
        preserve_sections: Sections that must not be removed.
    """
    rules = get_rules(format_name)
    max_pages = target_pages or rules.get("max_pages", 10)
    preserve = preserve_sections or ["abstract", "introduction", "conclusion"]

    style_result = check_style(tex, format_name, bibtex=bibtex)
    page_issues = [
        i for i in style_result.get("issues", [])
        if i.get("type") in ("page_limit", "page_minimum", "page_limit_warning")
    ]

    if not page_issues:
        # Content is already within limits
        return {
            "adapted": False,
            "tex": tex,
            "message": "Content already fits within format constraints",
            "estimated_pages": _estimate_pages(tex, format_name),
        }

    needs_trimming = any(
        i.get("type") == "page_limit" for i in page_issues
    )

    if needs_trimming:
        return await _trim_content(tex, format_name, max_pages, preserve)
    else:
        return await _expand_content(tex, format_name, max_pages, preserve)


async def _trim_content(
    tex: str,
    format_name: str,
    target_pages: int,
    preserve_sections: list[str],
) -> dict[str, Any]:
    """Use LLM to condense content to fit page limits."""
    preserve_str = ", ".join(preserve_sections)
    estimated = _estimate_pages(tex, format_name)

    prompt = (
        f"Condense the following LaTeX research paper to fit within {target_pages} pages.\n"
        f"Current estimated pages: ~{estimated}\n\n"
        f"Constraints:\n"
        f"1. MUST preserve these sections: {preserve_str}\n"
        f"2. Keep ALL citations (do not remove \\cite commands)\n"
        f"3. Keep ALL figures and tables (but can reduce their size)\n"
        f"4. Condense verbose descriptions, examples, and tangential discussions\n"
        f"5. Do NOT change the document structure (documentclass, packages, etc.)\n"
        f"6. Preserve the abstract and conclusion in full\n\n"
        f"LaTeX document:\n```\n{tex}\n```\n\n"
        f"Return a JSON object with:\n"
        f"- 'tex': The condensed LaTeX document\n"
        f"- 'changes': Array of changes made (e.g. 'Condensed Section 3 by 30%')\n"
        f"- 'estimated_pages': Estimated page count after condensing"
    )

    try:
        result = await agenerate_json(
            role="orchestrator",
            prompt=prompt,
            temperature=0.2,
            max_tokens=8192,
        )

        adapted_tex = result.get("tex", tex) if isinstance(result, dict) else tex
        return {
            "adapted": True,
            "action": "trimmed",
            "tex": adapted_tex,
            "changes": result.get("changes", ["LLM-trimmed content"]) if isinstance(result, dict) else [],
            "estimated_pages": result.get("estimated_pages", target_pages) if isinstance(result, dict) else target_pages,
            "message": f"Content condensed from ~{estimated} to ~{target_pages} pages",
        }
    except Exception as exc:
        logger.warning("LLM content trimming failed: %s", exc)
        return {
            "adapted": False,
            "action": "fallback",
            "tex": tex,
            "message": f"Automatic trim failed: {exc}",
            "estimated_pages": estimated,
        }


async def _expand_content(
    tex: str,
    format_name: str,
    target_pages: int,
    preserve_sections: list[str],
) -> dict[str, Any]:
    """Use LLM to expand content to meet minimum page requirements."""
    estimated = _estimate_pages(tex, format_name)

    prompt = (
        f"Expand the following LaTeX research paper to approximately {target_pages} pages.\n"
        f"Current estimated pages: ~{estimated}\n\n"
        f"Constraints:\n"
        f"1. Expand existing sections with more detailed explanations\n"
        f"2. Add relevant background context and related work discussion\n"
        f"3. Include more detailed methodology descriptions\n"
        f"4. Keep ALL existing citations and add relevant new ones\n"
        f"5. Do NOT change the document class or structure\n"
        f"6. Maintain academic tone and style\n\n"
        f"LaTeX document:\n```\n{tex}\n```\n\n"
        f"Return a JSON object with:\n"
        f"- 'tex': The expanded LaTeX document\n"
        f"- 'changes': Array of expansions made\n"
        f"- 'estimated_pages': Estimated page count after expansion"
    )

    try:
        result = await agenerate_json(
            role="orchestrator",
            prompt=prompt,
            temperature=0.2,
            max_tokens=8192,
        )

        adapted_tex = result.get("tex", tex) if isinstance(result, dict) else tex
        return {
            "adapted": True,
            "action": "expanded",
            "tex": adapted_tex,
            "changes": result.get("changes", ["LLM-expanded content"]) if isinstance(result, dict) else [],
            "estimated_pages": result.get("estimated_pages", target_pages) if isinstance(result, dict) else target_pages,
            "message": f"Content expanded from ~{estimated} to ~{target_pages} pages",
        }
    except Exception as exc:
        logger.warning("LLM content expansion failed: %s", exc)
        return {
            "adapted": False,
            "action": "fallback",
            "tex": tex,
            "message": f"Automatic expansion failed: {exc}",
            "estimated_pages": estimated,
        }


def _estimate_pages(tex: str, format_name: str) -> int:
    """Estimate page count for a LaTeX document."""
    rules = get_rules(format_name)
    chars_per_page = 2500 if rules.get("double_column") else 3000

    body_match = re.search(
        r"\\begin\{document\}(.*?)\\end\{document\}",
        tex,
        re.DOTALL,
    )
    body = body_match.group(1) if body_match else tex
    body = re.sub(r"\\bibliography[^}]*\}[^}]*\}", "", body)

    return max(1, len(body) // chars_per_page)
