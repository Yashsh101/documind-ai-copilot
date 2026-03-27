"""
FAISS-backed vector store with:
  - Cosine similarity (L2-normalised inner product)
  - Disk persistence (survives container restarts)
  - Thread-safe reads via asyncio.Lock
  - Relevance score filtering (skip low-quality chunks)
  - Incremental add support (append new documents without full rebuild)
"""
from __future__ import annotations

import asyncio
import pickle
from pathlib import Path

import faiss
import numpy as np

from app.config import get_settings
from app.services.ingestion import Chunk
from app.utils.exceptions import VectorStoreNotReadyError
from app.utils.logger import logger


class VectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self._dir = Path(settings.vector_store_dir)
        self._index_path = self._dir / "index.faiss"
        self._meta_path = self._dir / "metadata.pkl"
        self._index: faiss.Index | None = None
        self._chunks: list[Chunk] = []
        self._lock = asyncio.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    async def build(self, embeddings: np.ndarray, chunks: list[Chunk]) -> None:
        """Build a new index from scratch (called on first upload or full rebuild)."""
        async with self._lock:
            dim = embeddings.shape[1]
            index = faiss.IndexFlatIP(dim)   # Inner product on L2-normalised = cosine
            _normalise(embeddings)
            index.add(embeddings)
            self._index = index
            self._chunks = chunks
            self._persist()
            logger.info("vector_store_built", extra={"vectors": len(chunks), "dim": dim})

    async def add(self, embeddings: np.ndarray, chunks: list[Chunk]) -> None:
        """Append new documents to an existing index without a full rebuild."""
        if self._index is None:
            await self.build(embeddings, chunks)
            return
        async with self._lock:
            _normalise(embeddings)
            self._index.add(embeddings)
            self._chunks.extend(chunks)
            self._persist()
            logger.info("vector_store_updated", extra={"added": len(chunks)})

    async def search(self, query_embedding: np.ndarray, k: int | None = None) -> list[Chunk]:
        """Return top-k chunks sorted by cosine similarity, filtered by min score."""
        if self._index is None:
            raise VectorStoreNotReadyError()

        settings = get_settings()
        k = k or settings.top_k_retrieval

        async with self._lock:
            _normalise(query_embedding)
            scores, indices = self._index.search(query_embedding, k)

        results: list[Chunk] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            if float(score) < settings.min_relevance_score:
                continue
            chunk = self._chunks[idx]
            chunk.score = float(score)
            results.append(chunk)

        return results

    def load(self) -> bool:
        """Load persisted index from disk. Returns True if successful."""
        if not self._index_path.exists():
            return False
        try:
            self._index = faiss.read_index(str(self._index_path))
            self._chunks = pickle.loads(self._meta_path.read_bytes())
            logger.info("vector_store_loaded", extra={"vectors": len(self._chunks)})
            return True
        except Exception as exc:
            logger.warning("vector_store_load_failed", extra={"error": str(exc)})
            return False

    @property
    def is_ready(self) -> bool:
        return self._index is not None and self._index.ntotal > 0

    @property
    def total_chunks(self) -> int:
        return len(self._chunks)

    # ── Private ───────────────────────────────────────────────────────────────

    def _persist(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._index_path))
        self._meta_path.write_bytes(pickle.dumps(self._chunks))


def _normalise(arr: np.ndarray) -> None:
    """In-place L2 normalisation. Makes inner product equivalent to cosine similarity."""
    faiss.normalize_L2(arr)


# Module-level singleton — shared across all requests
vector_store = VectorStore()
