from __future__ import annotations

from typing import Any

from research_agent.chat.indexer import ChatLibraryIndex


async def answer_question(
    library_id: str,
    question: str,
    limit: int = 5
) -> dict[str, Any]:
    index = ChatLibraryIndex(library_id)
    chunks = await index.search(question, limit=limit)

    if not chunks:
        return {
            "answer": "No relevant documents found in this library.",
            "citations": [],
        }

    context = "\n\n".join(
        f"[{i+1}] {c.get('text', '')}" for i, c in enumerate(chunks)
    )

    answer = f"Based on {len(chunks)} relevant passages:\n\n{context}"

    citations = [
        {
            "index": i + 1,
            "text": c.get("text", "")[:100],
            "source": c.get("source_title", "") or c.get("source_url", ""),
        }
        for i, c in enumerate(chunks)
    ]

    return {"answer": answer, "citations": citations}
