from research_agent.observability import publish_progress
from research_agent.orchestration.nodes.indexing import get_or_create_index
from research_agent.orchestration.state import GraphState


def combiner_node(state: GraphState) -> dict:
    publish_progress(
        agent="Combiner",
        status="running",
        detail="Synthesizing section drafts via Deep RAG",
        message="Combining findings",
    )
    sections: list[dict[str, str]] = []
    index = get_or_create_index(state["run_id"])

    for task in state["tasks"]:
        task_id = str(task["task_id"])
        confidence = state["section_confidence"].get(task_id, 0.0)

        # Retrieve relevant chunks from the Deep RAG index
        query = f"{task['title']} {task['objective']}"
        hits = index.search(query, limit=6)

        evidence_parts = []
        for hit in hits:
            source = hit.get("source_title") or hit.get("source_url") or "Source"
            evidence_parts.append(f"[{source}]: {hit['text']}")

        evidence_text = "\n".join(evidence_parts) if evidence_parts else "No specific evidence chunks found."

        content = (
            f"Objective: {task['objective']}\n"
            f"Evidence (Deep RAG):\n{evidence_text}\n"
            f"Confidence score: {confidence:.2f}."
        )

        sections.append(
            {
                "task_id": task_id,
                "heading": str(task["title"]),
                "content": content,
            }
        )

    publish_progress(
        agent="Combiner",
        status="complete",
        detail=f"Synthesized {len(sections)} sections",
        message="Section synthesis complete",
    )
    return {
        "combined_sections": sections,
        "phase": "combined",
    }

