from __future__ import annotations

import os
import uuid
import hashlib
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from research_agent.rag.chunker import chunk_text


class ResearchIndex:
    def __init__(self, collection_name: str = "research_v1"):
        self.client = QdrantClient(":memory:")
        self.collection_name = collection_name
        self.vector_size = 384  # Default for many small local models
        self._seen_fingerprints: set[str] = set()
        self._inserted_points = 0
        self._skipped_duplicates = 0
        
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.vector_size,
                distance=models.Distance.COSINE
            ),
        )

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        # For v1, we use a simple deterministic "embedding" if no real model is available
        # In a real scenario, we'd use sentence-transformers or NVIDIA's embedding API
        # To keep it "free first" and low-dep, we use a hash-based pseudo-embedding
        # OR we check if NVIDIA_API_KEY is available for real embeddings
        
        api_key = os.getenv("NVIDIA_API_KEY")
        if api_key:
            try:
                from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
                embedder = NVIDIAEmbeddings(api_key=api_key)
                # Note: This is a synchronous call in v1 for simplicity
                return embedder.embed_documents(texts)
            except Exception:
                pass
        
        # Fallback: simple deterministic projection for "semantic" search mock
        import numpy as np
        
        def mock_embed(text: str) -> List[float]:
            state = np.random.RandomState(sum(ord(c) for c in text) % 2**32)
            return state.randn(self.vector_size).tolist()
            
        return [mock_embed(t) for t in texts]

    def add_finding(self, task_id: str, provider: str, item: Dict[str, Any]):
        text = item.get("snippet") or item.get("content") or item.get("title") or ""
        if not text:
            return
            
        chunks = chunk_text(text)
        if not chunks:
            return
            
        embeddings = self._get_embeddings(chunks)
        
        source_url = str(item.get("url") or "")
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            fp_raw = f"{source_url}::{chunk.strip().lower()}".encode("utf-8", errors="ignore")
            fingerprint = hashlib.sha1(fp_raw).hexdigest()
            if fingerprint in self._seen_fingerprints:
                self._skipped_duplicates += 1
                continue

            self._seen_fingerprints.add(fingerprint)
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "task_id": task_id,
                        "provider": provider,
                        "text": chunk,
                        "source_title": item.get("title"),
                        "source_url": item.get("url"),
                        "source_year": item.get("year"),
                        "chunk_fingerprint": fingerprint,
                    }
                )
            )

        if not points:
            return

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        self._inserted_points += len(points)

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        query_vector = self._get_embeddings([query])[0]
        
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit
        )
        
        return [hit.payload for hit in results.points if hit.payload]

    def get_stats(self) -> Dict[str, int]:
        return {
            "inserted_points": self._inserted_points,
            "skipped_duplicates": self._skipped_duplicates,
            "unique_fingerprints": len(self._seen_fingerprints),
        }
