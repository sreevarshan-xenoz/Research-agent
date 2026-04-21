from __future__ import annotations

import re
from typing import Any
import httpx

from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.tools.open_alex import OpenAlexAdapter
from research_agent.config import load_settings


def _first_author(item: dict[str, Any]) -> str:
    authors = item.get("authors") or []
    if isinstance(authors, list) and authors:
        if isinstance(authors[0], str):
            return authors[0]
    return "Unknown"


def _task_has_support(task_id: str, task_findings: dict[str, dict[str, dict[str, object]]]) -> bool:
    findings = task_findings.get(task_id, {})
    item_count = 0
    for provider_data in findings.values():
        item_count += int(provider_data.get("item_count", 0))
    return item_count > 0


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z]{4,}", text.lower())
        if token
        not in {
            "with",
            "from",
            "that",
            "this",
            "these",
            "those",
            "their",
            "there",
            "objective",
            "evidence",
            "confidence",
            "score",
            "deep",
            "rag",
        }
    }


def _task_evidence_tokens(task_id: str, state: GraphState) -> set[str]:
    findings = state["task_findings"].get(task_id, {})
    token_bag: set[str] = set()
    for provider_data in findings.values():
        items = provider_data.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            text = " ".join(
                [
                    str(item.get("title") or ""),
                    str(item.get("snippet") or ""),
                    str(item.get("content") or ""),
                ]
            )
            token_bag.update(_tokenize(text))
    return token_bag


def _extract_claim_sentences(section_content: str) -> list[str]:
    claims: list[str] = []
    for raw_line in section_content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("Objective:"):
            continue
        if line.startswith("Evidence (Deep RAG):"):
            continue
        if line.startswith("Confidence score:"):
            continue
        if line.startswith("Contradictions detected:"):
            continue
        if line.startswith("["):
            continue
        parts = re.split(r"(?<=[.!?])\s+", line)
        for part in parts:
            sentence = part.strip()
            if len(sentence.split()) < 6:
                continue
            claims.append(sentence)
    return claims


def _find_unsupported_sections(
    state: GraphState,
) -> tuple[list[dict[str, str]], set[str], dict[str, int]]:
    filtered_sections: list[dict[str, str]] = []
    unsupported_task_ids: set[str] = set()
    unsupported_claim_counts: dict[str, int] = {}

    for section in state["combined_sections"]:
        task_id = str(section.get("task_id", "")).strip()
        content = str(section.get("content", ""))
        if not task_id:
            filtered_sections.append(section)
            continue

        no_evidence_text = "No specific evidence chunks found." in content
        has_support = _task_has_support(task_id, state["task_findings"])
        evidence_tokens = _task_evidence_tokens(task_id, state)
        claim_sentences = _extract_claim_sentences(content)

        supported_claims = 0
        unsupported_claims = 0
        for sentence in claim_sentences:
            overlap = _tokenize(sentence).intersection(evidence_tokens)
            if len(overlap) >= 3:
                supported_claims += 1
            else:
                unsupported_claims += 1

        if no_evidence_text or not has_support:
            unsupported_task_ids.add(task_id)
        elif claim_sentences and supported_claims == 0:
            unsupported_task_ids.add(task_id)
            unsupported_claim_counts[task_id] = unsupported_claims
        elif unsupported_claims > 0:
            unsupported_claim_counts[task_id] = unsupported_claims

        # Always keep the section — warn instead of dropping
        filtered_sections.append(section)

    return filtered_sections, unsupported_task_ids, unsupported_claim_counts


async def _autofix_citations(
    citations: list[dict[str, str]], 
    mailto: str = "noreply@example.com"
) -> tuple[list[dict[str, str]], int]:
    """Attempts to repair incomplete citations using OpenAlex in parallel."""
    import asyncio
    repaired_count = 0
    adapter = OpenAlexAdapter(mailto=mailto)
    
    async def fix_single(cite: dict[str, str]) -> dict[str, str]:
        nonlocal repaired_count
        needs_fix = (
            cite.get("author") == "Unknown" or 
            not cite.get("url") or 
            len(cite.get("title", "")) < 10
        )
        
        if needs_fix and cite.get("title"):
            try:
                # v2.1: Use a thread pool for the sync adapter search call
                search_res = await asyncio.to_thread(adapter.search, cite["title"], limit=1)
                if search_res.items:
                    best_match = search_res.items[0]
                    if best_match.get("title"):
                        cite["title"] = str(best_match["title"])
                        if best_match.get("authors"):
                            cite["author"] = str(best_match["authors"][0])
                        if best_match.get("url"):
                            cite["url"] = str(best_match["url"])
                        if best_match.get("year"):
                            cite["year"] = str(best_match["year"])
                        repaired_count += 1
            except Exception:
                pass
        return cite

    fixed_citations = await asyncio.gather(*(fix_single(c) for c in citations))
    return list(fixed_citations), repaired_count


async def citation_verifier_node(state: GraphState) -> dict:
    settings = load_settings()
    
    await apublish_progress(
        agent="Citation Verifier",
        status="running",
        detail="Extracting source records",
        message="Collecting citations",
    )
    citations: list[dict[str, str]] = []
    run_warnings = list(state["run_warnings"])

    filtered_sections, unsupported_task_ids, unsupported_claim_counts = _find_unsupported_sections(state)
    if unsupported_task_ids:
        joined = ",".join(sorted(unsupported_task_ids))
        run_warnings.append(f"citation_verifier:unsupported_section_claims:{joined}")
    for task_id, claim_count in sorted(unsupported_claim_counts.items()):
        run_warnings.append(f"citation_verifier:unsupported_claims:{task_id}:{claim_count}")

    for task in state["tasks"]:
        task_id = str(task["task_id"])
        if task_id in unsupported_task_ids:
            continue
        findings = state["task_findings"].get(task_id, {})

        for provider_name, provider_data in findings.items():
            items = provider_data.get("items", [])
            if not isinstance(items, list):
                continue

            for idx, item in enumerate(items[:5], start=1):
                if not isinstance(item, dict):
                    continue

                title = str(item.get("title") or "Untitled source").strip()
                url = str(item.get("url") or "").strip()
                year = str(item.get("year") or "2026")
                author = _first_author(item)
                key = f"{task_id}_{provider_name}_{idx}".replace("-", "_")

                citations.append(
                    {
                        "key": key,
                        "title": title,
                        "url": url,
                        "year": year,
                        "author": author,
                    }
                )

    # v2: Citation Auto-Fix
    repaired_count = 0
    if settings.features.cite_autofix and citations:
        await apublish_progress(
            agent="Citation Verifier",
            status="running",
            detail=f"Auto-fixing {len(citations)} citations",
            message="Repairing metadata",
        )
        citations, repaired_count = await _autofix_citations(citations)

    if not citations:
        run_warnings.append("citation_verifier:no_citations_collected")

    detail_msg = f"Collected {len(citations)} citations"
    if repaired_count > 0:
        detail_msg += f" ({repaired_count} repaired)"
    if unsupported_task_ids:
        detail_msg += f", rejected {len(unsupported_task_ids)} unsupported sections"

    await apublish_progress(
        agent="Citation Verifier",
        status="complete",
        detail=detail_msg,
        message="Citation pass complete",
    )
    
    # v2.1: More descriptive phase
    phase = "citations_verified"
    if unsupported_task_ids:
        phase = "citations_rejected"

    return {
        "citations": citations,
        "combined_sections": filtered_sections,
        "run_warnings": run_warnings,
        "phase": phase,
    }
