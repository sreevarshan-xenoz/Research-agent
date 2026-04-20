from __future__ import annotations

import re
from typing import Any

from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


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


async def citation_verifier_node(state: GraphState) -> dict:
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

    if not citations:
        run_warnings.append("citation_verifier:no_citations_collected")

    await apublish_progress(
        agent="Citation Verifier",
        status="complete",
        detail=(
            f"Collected {len(citations)} citations"
            if not unsupported_task_ids
            else f"Collected {len(citations)} citations, rejected {len(unsupported_task_ids)} unsupported sections"
        ),
        message="Citation pass complete",
    )
    return {
        "citations": citations,
        "combined_sections": filtered_sections,
        "run_warnings": run_warnings,
        "phase": "citations_verified",
    }
