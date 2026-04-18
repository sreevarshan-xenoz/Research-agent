from __future__ import annotations

from research_agent.observability import publish_progress
from research_agent.orchestration.state import GraphState
from research_agent.rag.indexer import ResearchIndex


# We'll use a simple global cache for the index object in v1 
# to avoid serializing the Qdrant client, which isn't possible.
_INDEX_CACHE: dict[str, ResearchIndex] = {}


def get_or_create_index(run_id: str) -> ResearchIndex:
    if run_id not in _INDEX_CACHE:
        _INDEX_CACHE[run_id] = ResearchIndex(collection_name=f"run_{run_id}")
    return _INDEX_CACHE[run_id]


def indexing_node(state: GraphState) -> dict:
    run_id = state["run_id"]
    findings = state["task_findings"]
    
    publish_progress(
        agent="Indexer",
        status="running",
        detail="Indexing new findings",
        message="Building evidence base",
    )
    
    index = get_or_create_index(run_id)
    
    # Simple logic: index findings from the latest tasks that were just completed
    # For v1, we just re-index everything to be safe, or we could track indexed tasks.
    for task_id, provider_map in findings.items():
        for provider, result in provider_map.items():
            items = result.get("items", [])
            for item in items:
                index.add_finding(task_id, provider, item)
                
    publish_progress(
        agent="Indexer",
        status="complete",
        detail="Indexing complete",
        message="Deep RAG index updated",
    )
    
    return {"phase": "indexed"}
