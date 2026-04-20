from __future__ import annotations

import os
import uuid
import hashlib
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from research_agent.rag.chunker import chunk_text

# Global fingerprint cache for cross-run deduplication
# Key: fingerprint, Value: run_id when first seen
#
# NOTE: This is an in-memory cache only. For multi-worker deployments
# (separate processes), use Redis-backed cache or DB-level dedup.
# Current approach works for single-worker deployments (dev/small scale).
_GLOBAL_FINGERPRINT_CACHE: dict[str, str] = {}


class ResearchIndex:
    def __init__(self, collection_name: str = "research_v1", run_id: str = ""):
        self.client = QdrantClient(":memory:")
        self.collection_name = collection_name
        self.run_id = run_id
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

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        # For v1, we use a simple deterministic "embedding" if no real model is available
        # In a real scenario, we'd use sentence-transformers or NVIDIA's embedding API
        # To keep it "free first" and low-dep, we use a hash-based pseudo-embedding
        # OR we check if NVIDIA_API_KEY is available for real embeddings
        
        api_key = os.getenv("NVIDIA_API_KEY")
        enable_nvidia = os.getenv("ENABLE_NVIDIA_MODEL", "true").lower() not in ("0", "false")
        
        if api_key and enable_nvidia:
            try:
                from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
                embedder = NVIDIAEmbeddings(api_key=api_key)
                # Now using async call if available or running in thread
                import asyncio
                return await asyncio.to_thread(embedder.embed_documents, texts)
            except Exception:
                pass
        
        # Fallback: simple deterministic projection for "semantic" search mock
        import numpy as np
        
        def mock_embed(text: str) -> List[float]:
            state = np.random.RandomState(sum(ord(c) for c in text) % 2**32)
            return state.randn(self.vector_size).tolist()
            
        return [mock_embed(t) for t in texts]

    async def aadd_finding(self, task_id: str, provider: str, item: Dict[str, Any]):
        text = item.get("snippet") or item.get("content") or item.get("title") or ""
        if not text:
            return
            
        chunks = chunk_text(text)
        if not chunks:
            return
            
        embeddings = await self._get_embeddings(chunks)

        source_url = str(item.get("url") or "")
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            fp_raw = f"{source_url}::{chunk.strip().lower()}".encode("utf-8", errors="ignore")
            fingerprint = hashlib.sha1(fp_raw).hexdigest()

            # Check both local instance cache and global cross-run cache
            if fingerprint in self._seen_fingerprints or fingerprint in _GLOBAL_FINGERPRINT_CACHE:
                self._skipped_duplicates += 1
                continue

            self._seen_fingerprints.add(fingerprint)
            _GLOBAL_FINGERPRINT_CACHE[fingerprint] = self.run_id or "unknown"
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

    async def asearch(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        query_vectors = await self._get_embeddings([query])
        query_vector = query_vectors[0]
        
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
