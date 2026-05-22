from __future__ import annotations

from research_agent.models import agenerate_json
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


async def knowledge_graph_node(state: GraphState) -> dict:
    """Extracts a knowledge graph (entities and relations) from research findings."""
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

    await apublish_progress(
        agent="KG Extractor",
        status="complete",
        detail=f"Extracted {len(kg_data.get('nodes', [])) if kg_data else 0} nodes",
        message="Knowledge graph complete",
    )
    
    return {
        "knowledge_graph": kg_data,
        "phase": "kg_extracted"
    }
