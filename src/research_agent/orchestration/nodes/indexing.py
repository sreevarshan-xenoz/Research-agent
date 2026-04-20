from __future__ import annotations

import re

from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.rag.indexer import ResearchIndex


# We'll use a simple global cache for the index object in v1 
# to avoid serializing the Qdrant client, which isn't possible.
_INDEX_CACHE: dict[str, ResearchIndex] = {}
_CONTRADICTION_CACHE: dict[str, list[dict[str, str]]] = {}
_INDEXED_TASKS_CACHE: dict[str, set[str]] = {}

_NEGATIVE_TERMS = {
    "not",
    "no",
    "never",
    "fails",
    "failed",
    "cannot",
    "worse",
    "reduces",
    "ineffective",
    "risk",
}

_POSITIVE_TERMS = {
    "improves",
    "improved",
    "increase",
    "effective",
    "benefit",
    "better",
    "outperform",
    "supports",
    "reliable",
    "success",
}


def get_or_create_index(run_id: str) -> ResearchIndex:
    if run_id not in _INDEX_CACHE:
        _INDEX_CACHE[run_id] = ResearchIndex(collection_name=f"run_{run_id}", run_id=run_id)
    return _INDEX_CACHE[run_id]


def get_contradiction_links(run_id: str) -> list[dict[str, str]]:
    return list(_CONTRADICTION_CACHE.get(run_id, []))


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z]{4,}", text.lower())
        if token not in {"with", "from", "that", "this", "these", "those", "their", "there"}
    }


def _stance_score(text: str) -> int:
    lower = text.lower()
    positive_hits = sum(1 for term in _POSITIVE_TERMS if re.search(rf"\b{re.escape(term)}\b", lower))
    negative_hits = sum(1 for term in _NEGATIVE_TERMS if re.search(rf"\b{re.escape(term)}\b", lower))
    return positive_hits - negative_hits


def _collect_claim_records(findings: dict[str, dict[str, dict[str, object]]]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for task_id, provider_map in findings.items():
        for provider, result in provider_map.items():
            items = result.get("items", [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("snippet") or item.get("content") or item.get("title") or "").strip()
                if not text:
                    continue
                records.append(
                    {
                        "task_id": str(task_id),
                        "provider": str(provider),
                        "source": str(item.get("title") or item.get("url") or "source"),
                        "text": text,
                    }
                )
    return records


def _detect_contradictions(records: list[dict[str, str]]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    max_links = 50
    for i in range(len(records)):
        a = records[i]
        a_tokens = _tokenize(a["text"])
        if len(a_tokens) < 4:
            continue
        a_stance = _stance_score(a["text"])
        if a_stance == 0:
            continue

        for j in range(i + 1, len(records)):
            b = records[j]
            b_stance = _stance_score(b["text"])
            if b_stance == 0 or (a_stance > 0) == (b_stance > 0):
                continue

            b_tokens = _tokenize(b["text"])
            overlap = a_tokens.intersection(b_tokens)
            if len(overlap) < 3:
                continue

            links.append(
                {
                    "task_a": a["task_id"],
                    "task_b": b["task_id"],
                    "source_a": a["source"],
                    "source_b": b["source"],
                    "overlap_terms": ",".join(sorted(list(overlap))[:6]),
                }
            )
            if len(links) >= max_links:
                return links
    return links


async def indexing_node(state: GraphState) -> dict:
    run_id = state["run_id"]
    findings = state["task_findings"]
    run_warnings = list(state["run_warnings"])
    
    await apublish_progress(
        agent="Indexer",
        status="running",
        detail="Indexing new findings",
        message="Building evidence base",
    )
    
    index = get_or_create_index(run_id)
    indexed_task_ids = _INDEXED_TASKS_CACHE.get(run_id, set())
    
    new_points_before = index.get_stats().get("inserted_points", 0)
    
    # Only index tasks that haven't been indexed yet
    for task_id, provider_map in findings.items():
        if task_id in indexed_task_ids:
            continue
            
        for provider, result in provider_map.items():
            items = result.get("items", [])
            for item in items:
                await index.aadd_finding(task_id, provider, item)
        
        indexed_task_ids.add(task_id)

    _INDEXED_TASKS_CACHE[run_id] = indexed_task_ids
    new_points_after = index.get_stats().get("inserted_points", 0)
    inserted_this_run = new_points_after - new_points_before

    contradiction_links = _detect_contradictions(_collect_claim_records(findings))
    _CONTRADICTION_CACHE[run_id] = contradiction_links
    if contradiction_links:
        run_warnings.append(f"indexing:contradiction_links:{len(contradiction_links)}")
        for idx, link in enumerate(contradiction_links[:5], start=1):
            run_warnings.append(
                "contradiction_link:"
                f"{idx}:{link['task_a']}:{link['task_b']}:{link['overlap_terms']}"
            )
                
    await apublish_progress(
        agent="Indexer",
        status="complete",
        detail=(
            f"Indexing complete (new={inserted_this_run}, total={new_points_after}, "
            f"deduped={index.get_stats().get('skipped_duplicates', 0)}, "
            f"contradictions={len(contradiction_links)})"
        ),
        message="Deep RAG index updated",
    )
    
    return {
        "phase": "indexed",
        "run_warnings": run_warnings,
    }
