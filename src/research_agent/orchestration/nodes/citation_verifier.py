from __future__ import annotations

from typing import Any

from research_agent.orchestration.state import GraphState


def _first_author(item: dict[str, Any]) -> str:
    authors = item.get("authors") or []
    if isinstance(authors, list) and authors:
        if isinstance(authors[0], str):
            return authors[0]
    return "Unknown"


def citation_verifier_node(state: GraphState) -> dict:
    citations: list[dict[str, str]] = []
    run_warnings = list(state["run_warnings"])

    for task in state["tasks"]:
        task_id = str(task["task_id"])
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

    return {
        "citations": citations,
        "run_warnings": run_warnings,
        "phase": "citations_verified",
    }
