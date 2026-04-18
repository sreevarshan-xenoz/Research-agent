from research_agent.observability import publish_progress
from research_agent.orchestration.nodes.indexing import get_contradiction_links, get_or_create_index
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
    contradiction_links = get_contradiction_links(state["run_id"])

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
        task_contradictions = [
            link
            for link in contradiction_links
            if task_id in {link.get("task_a", ""), link.get("task_b", "")}
        ]

        contradiction_text = ""
        if task_contradictions:
            lines = [
                (
                    f"- {link.get('source_a', 'source A')} vs {link.get('source_b', 'source B')} "
                    f"(overlap: {link.get('overlap_terms', '')})"
                )
                for link in task_contradictions[:3]
            ]
            contradiction_text = "\nContradictions detected:\n" + "\n".join(lines)

        content = (
            f"Objective: {task['objective']}\n"
            f"Evidence (Deep RAG):\n{evidence_text}\n"
            f"{contradiction_text}\n"
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

