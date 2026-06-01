from __future__ import annotations


def chunk_text_semantic(
    text: str, chunk_size: int = 512, overlap: int = 50
) -> list[str]:
    if not text.strip():
        return []

    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap
        if start < 0:
            start = 0

    return chunks
