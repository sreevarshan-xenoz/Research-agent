from __future__ import annotations

import re
from typing import List
from research_agent.models import agenerate_text

async def extract_tables_from_text(raw_text: str) -> List[str]:
    """Uses LLM to identify and extract quantitative tables from unstructured PDF text."""
    if not raw_text or len(raw_text) < 200:
        return []

    prompt = (
        "Extract all quantitative data tables from the following unstructured text. "
        "Format them as clean GitHub-Flavored Markdown tables.\n\n"
        "Instructions:\n"
        "1. Identify rows and columns containing numbers, percentages, or comparisons.\n"
        "2. If no clear table exists, return 'NO_TABLES_FOUND'.\n"
        "3. Output ONLY the markdown tables.\n\n"
        "Unstructured Text:\n"
        f"{raw_text[:4000]}"
    )

    extracted = await agenerate_text(
        role="subagent",
        prompt=prompt,
        temperature=0.0,
        max_tokens=2000
    )

    if not extracted or "NO_TABLES_FOUND" in extracted:
        return []

    # Simple split by common markdown table markers if multiple
    tables = [t.strip() for t in extracted.split("\n\n") if "|" in t and "---" in t]
    return tables
