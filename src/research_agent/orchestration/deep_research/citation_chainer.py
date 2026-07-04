from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Maximum chain depth to prevent runaway recursion
_MAX_CHAIN_DEPTH = 2
# Maximum papers to chain from per task
_MAX_SEED_PAPERS = 3
# Maximum total chained papers per task
_MAX_CHAINED_PAPERS = 15


@dataclass
class CitationChainResult:
    """Result of a citation chaining run."""

    chained_papers: list[dict[str, Any]] = field(default_factory=list)
    seed_papers_used: list[str] = field(default_factory=list)
    chain_depth: int = 0
    total_fetched: int = 0
    warnings: list[str] = field(default_factory=list)


async def chain_citations(
    registry: dict[str, Any],
    task_findings: dict[str, Any],
    max_depth: int = _MAX_CHAIN_DEPTH,
    max_seed_papers: int = _MAX_SEED_PAPERS,
    max_total: int = _MAX_CHAINED_PAPERS,
) -> CitationChainResult:
    """Recursively fetch citations and references for high-value papers.

    Identifies seed papers from task findings (prioritized by citation count),
    then fetches their citing papers and references via Semantic Scholar.
    Continues recursively up to ``max_depth`` levels.

    Args:
        registry: Tool registry containing 'semantic_scholar' adapter
        task_findings: Current task findings (provider -> {items, ...})
        max_depth: Maximum recursion depth for citation chains
        max_seed_papers: Number of top seed papers to chain from
        max_total: Maximum total chained papers to return

    Returns:
        CitationChainResult with deduplicated chained papers and metadata
    """
    ss_adapter = registry.get("semantic_scholar")
    if ss_adapter is None:
        return CitationChainResult(warnings=["semantic_scholar not in registry; citation chaining skipped"])

    # Collect all papers from findings, deduplicate by paper_id
    seen_ids: set[str] = set()
    seed_candidates: list[dict[str, Any]] = []

    for provider_data in task_findings.values():
        if not isinstance(provider_data, dict):
            continue
        items = provider_data.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            paper_id = item.get("paper_id") or ""
            if paper_id and paper_id not in seen_ids:
                seen_ids.add(paper_id)
                seed_candidates.append(item)

    if not seed_candidates:
        return CitationChainResult(warnings=["No seed papers found for citation chaining"])

    # Sort by citation count descending, take top N
    seed_candidates.sort(
        key=lambda p: (
            int(p.get("citation_count", 0) or 0),
            int(p.get("year", 0) or 0),
        ),
        reverse=True,
    )
    seeds = seed_candidates[:max_seed_papers]

    result = CitationChainResult(
        seed_papers_used=[s.get("paper_id", "") for s in seeds if s.get("paper_id")],
        chain_depth=max_depth,
    )

    # BFS-style recursive chain
    all_chained: list[dict[str, Any]] = []
    chained_ids: set[str] = set()
    current_level = [(s.get("paper_id", ""), s.get("title", "")) for s in seeds if s.get("paper_id")]
    depth = 0

    while current_level and depth < max_depth and len(all_chained) < max_total:
        next_level: list[tuple[str, str]] = []
        batch_tasks = []

        for pid, ptitle in current_level:
            if pid in chained_ids:
                continue
            chained_ids.add(pid)
            batch_tasks.append(_fetch_citation_neighbors(ss_adapter, pid, ptitle))

        if not batch_tasks:
            break

        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        for batch_result in batch_results:
            if isinstance(batch_result, BaseException):
                result.warnings.append(f"citation_chain_fetch_error:{batch_result}")
                continue

            citations, references, _warnings = batch_result
            result.warnings.extend(_warnings)
            result.total_fetched += len(citations) + len(references)

            for paper in citations + references:
                if not isinstance(paper, dict):
                    continue
                pid = paper.get("paper_id") or ""
                if pid and pid not in chained_ids:
                    chained_ids.add(pid)
                    all_chained.append(paper)
                    if len(all_chained) >= max_total:
                        break
                    next_level.append((pid, str(paper.get("title", ""))))

            if len(all_chained) >= max_total:
                break

        current_level = next_level
        depth += 1

    result.chained_papers = all_chained[:max_total]
    result.chain_depth = depth
    return result


async def _fetch_citation_neighbors(
    ss_adapter: Any,
    paper_id: str,
    paper_title: str,
    limit: int = 10,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Fetch both citing papers and references for a single paper in parallel."""
    warnings: list[str] = []

    async def _fetch_citations() -> list[dict[str, Any]]:
        try:
            res = await asyncio.to_thread(
                ss_adapter.get_citations_for_paper, paper_id, limit=limit
            )
            return [item for item in res.items if isinstance(item, dict)]
        except Exception as exc:
            warnings.append(f"citations_fetch:{paper_id}:{exc}")
            return []

    async def _fetch_references() -> list[dict[str, Any]]:
        try:
            res = await asyncio.to_thread(
                ss_adapter.get_references_for_paper, paper_id, limit=limit
            )
            return [item for item in res.items if isinstance(item, dict)]
        except Exception as exc:
            warnings.append(f"references_fetch:{paper_id}:{exc}")
            return []

    citations_task = _fetch_citations()
    references_task = _fetch_references()

    citations, references = await asyncio.gather(citations_task, references_task)

    # Annotate with source info
    for c in citations:
        c["_chained_from"] = paper_id
        c["_chained_type"] = "citing"
    for r in references:
        r["_chained_from"] = paper_id
        r["_chained_type"] = "cited"

    return citations, references, warnings
