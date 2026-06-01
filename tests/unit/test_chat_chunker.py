import pytest
from research_agent.chat.chunker import chunk_text_semantic

def test_chunk_text_semantic():
    text = "Hello. " * 100
    chunks = chunk_text_semantic(text, chunk_size=100, overlap=20)
    assert len(chunks) >= 1
    assert all(len(c.split()) <= 120 for c in chunks)

def test_chunk_text_empty():
    assert chunk_text_semantic("") == []

def test_chunk_text_short():
    chunks = chunk_text_semantic("Short text.", chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == "Short text."
