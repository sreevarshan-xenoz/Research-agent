from __future__ import annotations

import re
from typing import List


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks.
    
    A simple character-based splitter with overlap for v1.
    """
    if not text:
        return []
    
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
        
    return chunks
