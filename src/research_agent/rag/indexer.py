from __future__ import annotations

import asyncio
import logging
import os
import uuid
import hashlib
import random
from typing import Any, Dict, List
from collections import OrderedDict

from qdrant_client import QdrantClient
from qdrant_client.http import models

from research_agent.config import load_settings
from research_agent.rag.chunker import chunk_text


logger = logging.getLogger(__name__)


class LRUCache(OrderedDict):
    """Simple LRU cache for fingerprints to prevent memory leaks."""
    def __init__(self, capacity: int = 10000):
        super().__init__()
        self.capacity = capacity

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.capacity:
            self.popitem(last=False)

# Global fingerprint cache for cross-run deduplication
_GLOBAL_FINGERPRINT_CACHE = LRUCache(capacity=50000)
_FINGERPRINT_CACHE_LOCK = asyncio.Lock()


class ResearchIndex:
    def __init__(self, collection_name: str = "research_v1", run_id: str = ""):
        settings = load_settings()
        location = settings.qdrant.location
        if location == ":memory:":
            self.client = QdrantClient(":memory:")
        elif location.startswith("http://") or location.startswith("https://"):
            self.client = QdrantClient(url=location)
        else:
            # Assume it's a file path
            os.makedirs(location, exist_ok=True)
            self.client = QdrantClient(path=location)
            
        self.collection_name = collection_name
        self.run_id = run_id
        self.vector_size = 384  # Fallback for deterministic local embeddings.
        self._collection_created = False
        self._lock = asyncio.Lock()  # Guards _ensure_collection, _get_embeddings, _seen_fingerprints
        self._seen_fingerprints: set[str] = set()
        self._inserted_points = 0
        self._skipped_duplicates = 0

    def close(self) -> None:
        """Close the underlying Qdrant client and release connections.

        Safe to call multiple times. Once closed, the instance should not be reused.
        For :memory: and local-path modes this is a no-op.
        """
        try:
            self.client.close()
        except Exception:
            pass

    def _clear_local_fingerprints(self) -> None:
        """Reset the instance-level seen fingerprints set.

        Called after indexing to free memory. The global fingerprint cache
        still prevents cross-run re-indexing of duplicates.
        """
        self._seen_fingerprints.clear()

    def _ensure_collection(self, vector_size: int) -> None:
        # NOTE: Callers must hold self._lock
        # Verify if the collection already exists in Qdrant and check its dimensions
        try:
            info = self.client.get_collection(self.collection_name)
            if info is not None and info.config is not None and info.config.params is not None:
                vectors_cfg = info.config.params.vectors
                existing_size = 0
                if vectors_cfg is not None:
                    if isinstance(vectors_cfg, dict):
                        first_val = next(iter(vectors_cfg.values()), None)
                        if first_val is not None:
                            existing_size = getattr(first_val, "size", 0)
                    else:
                        existing_size = getattr(vectors_cfg, "size", 0)
                
                if existing_size != vector_size:
                    logger.info(
                        "Recreating collection '%s' due to vector dimension change from %d to %d",
                        self.collection_name,
                        existing_size,
                        vector_size,
                    )
                    self.client.delete_collection(collection_name=self.collection_name)
                    self._collection_created = False
                else:
                    # Dimensions match, so the collection is ready
                    self.vector_size = vector_size
                    self._collection_created = True
        except Exception:
            # Collection does not exist or failed to query, will create below
            pass

        if self._collection_created and vector_size == self.vector_size:
            return

        if self._collection_created:
            try:
                self.client.delete_collection(collection_name=self.collection_name)
            except Exception:
                pass

        self.vector_size = vector_size
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.vector_size,
                distance=models.Distance.COSINE
            ),
        )
        self._collection_created = True


    def _coerce_vector(self, vector: List[float]) -> List[float]:
        """Pad or truncate a vector to match self.vector_size.

        Safe to call without a lock because _get_embeddings() always runs
        first (under self._lock) and sets self.vector_size before returning.
        """
        if len(vector) == self.vector_size:
            return vector
        if len(vector) > self.vector_size:
            return vector[: self.vector_size]
        return vector + [0.0] * (self.vector_size - len(vector))

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Compute embeddings and ensure the Qdrant collection is created.

        Every path in this method calls self._ensure_collection() under
        self._lock after the vector size is determined, guaranteeing the
        collection exists before aadd_finding() or asearch() use it.
        """
        settings = load_settings()
        embedding_model = settings.retrieval.embedding_model
        
        embedding_providers = [
            ("sentence_transformers", embedding_model),
            ("openai", settings.openai.api_key.get_secret_value() if settings.openai.api_key else os.getenv("OPENAI_API_KEY", "")),
            ("nvidia", os.getenv("NVIDIA_API_KEY", "") or os.getenv("NVIDIA_NIMS_API_KEY", "")),
        ]

        for prov_name, prov_config in embedding_providers:
            if prov_name == "sentence_transformers" and prov_config and settings.features.multi_language:
                try:
                    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
                    async with self._lock:
                        if not hasattr(self, "_st_model"):
                            self._st_model = SentenceTransformer(prov_config)
                        dim = self._st_model.get_sentence_embedding_dimension()
                        if dim is not None:
                            self.vector_size = dim
                        self._ensure_collection(self.vector_size)
                    embeddings = await asyncio.to_thread(self._st_model.encode, texts)
                    logger.info("Using sentence-transformers embeddings (%s)", prov_config)
                    return embeddings.tolist()
                except ImportError:
                    logger.info("sentence-transformers not installed — trying next embedding provider")
                except Exception as exc:
                    logger.warning("sentence-transformers embedding failed: %s — trying next provider", exc)

            elif prov_name == "openai" and prov_config:
                try:
                    import openai
                    client = openai.AsyncOpenAI(api_key=prov_config)
                    response = await client.embeddings.create(
                        model="text-embedding-3-small",
                        input=texts,
                    )
                    embeddings = [item.embedding for item in response.data]
                    if embeddings:
                        async with self._lock:
                            vs = len(embeddings[0])
                            if vs != self.vector_size:
                                self.vector_size = vs
                            self._ensure_collection(self.vector_size)
                    logger.info("Using OpenAI embeddings (text-embedding-3-small)")
                    return embeddings
                except ImportError:
                    logger.info("openai package not installed — trying next embedding provider")
                except Exception as exc:
                    logger.warning("OpenAI embedding failed: %s — trying next provider", exc)

            elif prov_name == "nvidia" and prov_config:
                try:
                    from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings  # type: ignore[import-untyped]
                    embedder = NVIDIAEmbeddings(api_key=prov_config)
                    embeddings = await asyncio.to_thread(embedder.embed_documents, texts)
                    if embeddings:
                        async with self._lock:
                            vs = len(embeddings[0])
                            if vs != self.vector_size:
                                self.vector_size = vs
                            self._ensure_collection(self.vector_size)
                    logger.info("Using NVIDIA embeddings")
                    return embeddings
                except ImportError:
                    logger.info("langchain-nvidia package not installed — falling back to deterministic")
                except Exception as exc:
                    logger.warning("NVIDIA embedding failed: %s — falling back to deterministic", exc)

        # Final fallback: simple deterministic projection for "semantic" search mock
        async with self._lock:
            self._ensure_collection(self.vector_size)
            logger.info("Falling back to deterministic mock embeddings (no provider available)")
            def mock_embed(text: str) -> List[float]:
                seed = sum(ord(c) for c in text) % 2**32
                rng = random.Random(seed)
                return [rng.uniform(-1, 1) for _ in range(self.vector_size)]
            return [mock_embed(t) for t in texts]

    async def aadd_finding(self, task_id: str, provider: str, item: Dict[str, Any]):
        text = item.get("snippet") or item.get("content") or item.get("title") or ""
        if not text:
            return
            
        chunks = chunk_text(text)
        if not chunks:
            return

        embeddings = []
        for vector in await self._get_embeddings(chunks):
            embeddings.append(self._coerce_vector(vector))

        source_url = str(item.get("url") or "")
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            fp_raw = f"{source_url}::{chunk.strip().lower()}".encode("utf-8", errors="ignore")
            fingerprint = hashlib.sha1(fp_raw).hexdigest()

            # Check both local instance cache and global cross-run cache
            async with self._lock:
                if fingerprint in self._seen_fingerprints:
                    self._skipped_duplicates += 1
                    continue
            async with _FINGERPRINT_CACHE_LOCK:
                if fingerprint in _GLOBAL_FINGERPRINT_CACHE:
                    self._skipped_duplicates += 1
                    continue
                _GLOBAL_FINGERPRINT_CACHE[fingerprint] = self.run_id or "unknown"

            async with self._lock:
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

    async def asearch(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        query_vectors = await self._get_embeddings([query])
        query_vector = self._coerce_vector(query_vectors[0])
        
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


async def reset_fingerprint_cache() -> None:
    """Reset the global fingerprint cache.

    Useful for testing or when a full re-index is desired.
    """
    global _GLOBAL_FINGERPRINT_CACHE
    async with _FINGERPRINT_CACHE_LOCK:
        _GLOBAL_FINGERPRINT_CACHE = LRUCache(capacity=50000)
