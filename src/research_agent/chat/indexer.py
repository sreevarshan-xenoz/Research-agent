from __future__ import annotations

from typing import Any

from research_agent.rag.indexer import ResearchIndex


class ChatLibraryIndex:
    def __init__(self, library_id: str):
        self.library_id = library_id
        collection = f"chat_{library_id}"
        self.index = ResearchIndex(collection_name=collection)

    async def add_document(self, text: str, metadata: dict[str, Any]) -> int:
        chunks = self._chunk(text)
        for chunk in chunks:
            await self.index.aadd_finding(
                task_id="chat_upload",
                provider="user_upload",
                item={
                    "snippet": chunk,
                    "title": metadata.get("title", ""),
                    "url": metadata.get("source", ""),
                    "content": chunk,
                }
            )
        return len(chunks)

    def _chunk(self, text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
        words = text.split()
        if len(words) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunks.append(" ".join(words[start:end]))
            start = end - overlap
            if start < 0:
                start = 0
        return chunks

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return await self.index.asearch(query, limit=limit)
