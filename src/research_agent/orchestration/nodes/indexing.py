from __future__ import annotations

import asyncio
import re
import time

from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.rag.indexer import ResearchIndex


# Global caches with asyncio locks for thread-safe concurrent access.
# These are safe for multiple concurrent runs since each run_id is isolated.
# Bounded to prevent unbounded memory growth across many runs.
# Cache entries older than MAX_CACHE_AGE_SECONDS are purged on access.
_MAX_CACHED_RUNS = 100
_MAX_CACHE_AGE_SECONDS = 3600  # 1 hour

_INDEX_CACHE: dict[str, ResearchIndex] = {}
_INDEX_CACHE_LOCK = asyncio.Lock()
_INDEX_CACHE_TIMESTAMPS: dict[str, float] = {}  # run_id -> creation time

_CONTRADICTION_CACHE: dict[str, list[dict[str, str]]] = {}
_CONTRADICTION_CACHE_LOCK = asyncio.Lock()

_INDEXED_TASKS_CACHE: dict[str, set[str]] = {}
_INDEXED_TASKS_CACHE_LOCK = asyncio.Lock()

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


def _purge_stale_index_cache(max_runs: int = _MAX_CACHED_RUNS) -> int:
    """Evict old entries when cache exceeds max_runs.

    NOTE: Only evicts from _INDEX_CACHE / _INDEX_CACHE_TIMESTAMPS.
    The other caches (_CONTRADICTION_CACHE, _INDEXED_TASKS_CACHE) are
    cleaned up by cleanup_run_state() (called from run_graph() finally
    block) to avoid cross-lock races.

    Must be called under _INDEX_CACHE_LOCK.

    Returns number of evicted entries.
    """
    if len(_INDEX_CACHE) <= max_runs:
        return 0

    # Sort by timestamp (oldest first) and remove excess
    sorted_ids = sorted(
        _INDEX_CACHE_TIMESTAMPS.keys(),
        key=lambda rid: _INDEX_CACHE_TIMESTAMPS[rid],
    )
    to_remove = sorted_ids[: len(_INDEX_CACHE) - max_runs]
    for rid in to_remove:
        _INDEX_CACHE.pop(rid, None)
        _INDEX_CACHE_TIMESTAMPS.pop(rid, None)
    return len(to_remove)


async def get_or_create_index(run_id: str) -> ResearchIndex:
    async with _INDEX_CACHE_LOCK:
        _purge_stale_index_cache()
        if run_id not in _INDEX_CACHE:
            _INDEX_CACHE[run_id] = ResearchIndex(collection_name=f"run_{run_id}", run_id=run_id)
            _INDEX_CACHE_TIMESTAMPS[run_id] = time.time()
        return _INDEX_CACHE[run_id]


async def get_contradiction_links(run_id: str) -> list[dict[str, str]]:
    async with _CONTRADICTION_CACHE_LOCK:
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
    
    index = await get_or_create_index(run_id)
    async with _INDEXED_TASKS_CACHE_LOCK:
        indexed_task_ids = set(_INDEXED_TASKS_CACHE.get(run_id, set()))
    
    new_points_before = index.get_stats().get("inserted_points", 0)
    
    # Only index tasks that haven't been indexed yet
    newly_indexed: set[str] = set()
    for task_id, provider_map in findings.items():
        if task_id in indexed_task_ids:
            continue
            
        for provider, result in provider_map.items():
            if isinstance(result, dict):
                items = result.get("items", [])
                if isinstance(items, list):
                    for item in items:
                        await index.aadd_finding(task_id, provider, item)
        newly_indexed.add(task_id)

    if newly_indexed:
        async with _INDEXED_TASKS_CACHE_LOCK:
            # Re-read in case another task updated the cache while we were indexing
            current = set(_INDEXED_TASKS_CACHE.get(run_id, set()))
            current.update(newly_indexed)
            _INDEXED_TASKS_CACHE[run_id] = current
    new_points_after = index.get_stats().get("inserted_points", 0)
    inserted_this_run = new_points_after - new_points_before

    contradiction_links = _detect_contradictions(_collect_claim_records(findings))
    async with _CONTRADICTION_CACHE_LOCK:
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


async def cleanup_run_state(run_id: str) -> None:
    """Remove all cached state for a given run_id from module-level caches.

    Called by run_graph() finally block to prevent memory leaks.
    Closes the QdrantClient for the evicted index to prevent connection leaks.
    Safe to call multiple times — no-op if run_id not in cache.
    """
    async with _INDEX_CACHE_LOCK:
        index = _INDEX_CACHE.pop(run_id, None)
        _INDEX_CACHE_TIMESTAMPS.pop(run_id, None)
    if index is not None:
        # Close the Qdrant client in a thread to avoid blocking the event loop.
        # QdrantClient.close() is a synchronous method (httpx.Client.close).
        await asyncio.to_thread(index.close)
        # Release the instance-level fingerprint set to free memory.
        index._clear_local_fingerprints()
    async with _CONTRADICTION_CACHE_LOCK:
        _CONTRADICTION_CACHE.pop(run_id, None)
    async with _INDEXED_TASKS_CACHE_LOCK:
        _INDEXED_TASKS_CACHE.pop(run_id, None)
