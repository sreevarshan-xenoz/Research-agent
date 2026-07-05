from __future__ import annotations

from research_agent.models import agenerate_json
from research_agent.observability import apublish_progress
from research_agent.observability.logging import ErrorSeverity, log_error
from research_agent.orchestration.state import GraphState
from research_agent.rag import KnowledgeGraphStore


async def knowledge_graph_node(state: GraphState) -> dict:
    """Extracts a knowledge graph (entities and relations) from research findings
    and persists it across runs via KnowledgeGraphStore."""
    await apublish_progress(
        agent="KG Extractor",
        status="running",
        detail="Extracting entities and relations",
        message="Synthesizing knowledge graph",
    )
    
    sections = state.get("combined_sections", [])
    if not sections:
        return {"phase": "kg_skipped"}

    # Use first few sections for KG extraction to keep context manageable
    context = "\n".join([
        f"Section: {s.get('heading')}\nContent: {s.get('content', '')[:1000]}"
        for s in sections[:5]
    ])

    prompt = (
        "You are a knowledge engineer. Extract a high-level knowledge graph from the following research summary.\n\n"
        f"Topic: {state['topic']}\n\n"
        "Research Context:\n"
        f"{context}\n\n"
        "Instructions:\n"
        "1. Identify the most important entities (Models, Datasets, Methods, Authors, Organizations).\n"
        "2. Identify the key relationships between them (e.g., 'Model X used Dataset Y', 'Method A improves on Method B').\n"
        "3. Output a JSON object with two keys: 'nodes' (list of dicts with 'id', 'label', 'type') and 'edges' (list of dicts with 'source', 'target', 'relation').\n"
        "4. Limit to the top 15-20 most significant nodes.\n"
    )

    kg_data = await agenerate_json(
        role="orchestrator",
        prompt=prompt,
        temperature=0.2,
        max_tokens=2000
    )

    node_count = 0
    if isinstance(kg_data, dict):
        node_count = len(kg_data.get("nodes", []))

    # Persist extracted entities/relations into KnowledgeGraphStore
    if isinstance(kg_data, dict):
        try:
            run_id = state.get("run_id", "default")
            kg_store = KnowledgeGraphStore(run_id=run_id)
            
            # Add entities
            for node in kg_data.get("nodes", []):
                node_id = node.get("id", "")
                node_type = node.get("type", "Unknown")
                properties = {k: v for k, v in node.items() if k not in ("id", "type")}
                kg_store.add_entity(node_id, node_type, properties)
            
            # Add relations
            for edge in kg_data.get("edges", []):
                source = edge.get("source", "")
                target = edge.get("target", "")
                relation = edge.get("relation", "related_to")
                properties = {k: v for k, v in edge.items() if k not in ("source", "target", "relation")}
                kg_store.add_relation(source, target, relation, properties)
            
            # Save to disk for persistence across runs
            kg_store.save_graph()
            
        except Exception as exc:
            log_error(
                "Failed to persist knowledge graph",
                severity=ErrorSeverity.RECOVERABLE,
                component="kg_extractor",
                detail=f"{type(exc).__name__}: {exc}",
            )

    await apublish_progress(
        agent="KG Extractor",
        status="complete",
        detail=f"Extracted {node_count} nodes",
        message="Knowledge graph complete",
    )
    
    return {
        "knowledge_graph": kg_data if isinstance(kg_data, dict) else {},
        "phase": "kg_extracted"
    }
