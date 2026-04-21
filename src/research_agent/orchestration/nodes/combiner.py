from research_agent.models import agenerate_text
from research_agent.observability import apublish_progress
from research_agent.orchestration.nodes.indexing import get_contradiction_links, get_or_create_index
from research_agent.orchestration.state import GraphState


async def combiner_node(state: GraphState) -> dict:
    await apublish_progress(
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
        hits = await index.asearch(query, limit=10)

        evidence_parts = []
        for i, hit in enumerate(hits):
            source = hit.get("source_title") or hit.get("source_url") or "Source"
            # Provide a stable reference key for the LLM to use
            ref_key = f"REF{i+1}"
            evidence_parts.append(f"[{ref_key}] ({source}): {hit['text']}")

        evidence_text = "\n".join(evidence_parts) if evidence_parts else "No specific evidence chunks found."
        
        task_contradictions = [
            link
            for link in contradiction_links
            if task_id in {link.get("task_a", ""), link.get("task_b", "")}
        ]

        contradiction_text = "No contradictions detected between sources."
        if task_contradictions:
            lines = [
                (
                    f"- {link.get('source_a', 'source A')} vs {link.get('source_b', 'source B')} "
                    f"(overlap: {link.get('overlap_terms', '')})"
                )
                for link in task_contradictions[:3]
            ]
            contradiction_text = "\nContradictions detected to address:\n" + "\n".join(lines)

        # Grounded synthesis prompt
        prompt = (
            f"You are a research synthesizer. Write a technical section for the topic: '{state['topic']}'.\n\n"
            f"Section Title: {task['title']}\n"
            f"Objective: {task['objective']}\n\n"
            "Use the following evidence retrieved via Deep RAG. "
            "IMPORTANT: Use the reference keys like [REF1], [REF2] exactly as provided to cite your claims.\n\n"
            f"Evidence:\n{evidence_text}\n\n"
            f"Verification Context:\n{contradiction_text}\n\n"
            "Write 2-3 detailed paragraphs. Be objective and technical. "
            "If contradictions are present, acknowledge the differing viewpoints."
        )

        content = await agenerate_text(role="subagent", prompt=prompt)
        if not content:
            # Fallback to crude synthesis
            content = (
                f"Objective: {task['objective']}\n"
                f"Evidence Summary:\n{evidence_text[:500]}...\n"
                f"Confidence: {confidence:.2f}"
            )

        # Build citation map: REF number -> source info for composer to use
        # v2.1: Use URL as stable source key
        citation_map = {}
        for i, hit in enumerate(hits):
            ref_key = f"REF{i+1}"
            url = hit.get("source_url") or f"internal://{hashlib.sha1(hit['text'].encode()).hexdigest()[:8]}"
            citation_map[ref_key] = {
                "title": hit.get("source_title") or hit.get("source_url") or "Source",
                "url": url,
                "provider": hit.get("source_type") or "web",
            }

        sections.append(
            {
                "task_id": task_id,
                "heading": str(task["title"]),
                "content": content,
                "raw_evidence": evidence_text,
                "citation_map": citation_map,  # Proper mapping for composer
            }
        )

    await apublish_progress(
        agent="Combiner",
        status="complete",
        detail=f"Synthesized {len(sections)} sections",
        message="Section synthesis complete",
    )
    return {
        "combined_sections": sections,
        "phase": "combined",
    }

