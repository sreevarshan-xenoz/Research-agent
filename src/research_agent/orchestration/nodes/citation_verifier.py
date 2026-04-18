from __future__ import annotations

from typing import Any

from research_agent.observability import publish_progress
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


def _find_unsupported_sections(state: GraphState) -> tuple[list[dict[str, str]], set[str]]:
    filtered_sections: list[dict[str, str]] = []
    unsupported_task_ids: set[str] = set()

    for section in state["combined_sections"]:
        task_id = str(section.get("task_id", "")).strip()
        content = str(section.get("content", ""))
        if not task_id:
            filtered_sections.append(section)
            continue

        no_evidence_text = "No specific evidence chunks found." in content
        has_support = _task_has_support(task_id, state["task_findings"])
        if no_evidence_text or not has_support:
            unsupported_task_ids.add(task_id)
            continue

        filtered_sections.append(section)

    return filtered_sections, unsupported_task_ids


def citation_verifier_node(state: GraphState) -> dict:
    publish_progress(
        agent="Citation Verifier",
        status="running",
        detail="Extracting source records",
        message="Collecting citations",
    )
    citations: list[dict[str, str]] = []
    run_warnings = list(state["run_warnings"])

    filtered_sections, unsupported_task_ids = _find_unsupported_sections(state)
    if unsupported_task_ids:
        joined = ",".join(sorted(unsupported_task_ids))
        run_warnings.append(f"citation_verifier:unsupported_section_claims:{joined}")

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

    publish_progress(
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
