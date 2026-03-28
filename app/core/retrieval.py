from __future__ import annotations
import asyncio, pickle, re
from pathlib import Path
import faiss, numpy as np
from rank_bm25 import BM25Okapi

from app.config import get_settings
from app.utils.helpers import VectorStoreNotReadyError
from app.utils.logger import logger

# --- BM25 Sparse Index ---
class BM25Index:
    def __init__(self):
        s = get_settings()
        self._path = Path(s.vector_store_dir) / "bm25.pkl"
        self._index: BM25Okapi | None = None
        self._chunks: list = []

    def build(self, chunks: list) -> None:
        self._chunks = chunks
        corpus = [self._tokenise(c.text) for c in chunks]
        self._index = BM25Okapi(corpus)
        self._save()
        logger.info(f"BM25 index built with {len(chunks)} docs")

    def search(self, query: str, k: int = 20) -> list[tuple]:
        """Returns list of (chunk, bm25_score) sorted descending."""
        if not self._index or not self._chunks:
            return []
        tokens = self._tokenise(query)
        scores = self._index.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in ranked[:k]:
            if score > 0:
                results.append((self._chunks[idx], float(score)))
        return results

    def load(self) -> bool:
        if not self._path.exists(): return False
        try:
            data = pickle.loads(self._path.read_bytes())
            self._index = data["index"]
            self._chunks = data["chunks"]
            logger.info(f"BM25 index loaded: {len(self._chunks)} docs")
            return True
        except Exception as e:
            logger.warning(f"BM25 load failed: {e}")
            return False

    def _tokenise(self, text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(pickle.dumps({
            "index": self._index, "chunks": self._chunks}))

# --- FAISS Dense Vector Store ---
class VectorStore:
    def __init__(self):
        s = get_settings()
        self._dir = Path(s.vector_store_dir)
        self._idx_path = self._dir/"index.faiss"
        self._meta_path = self._dir/"metadata.pkl"
        self._index = None
        self._chunks = []
        self._lock = asyncio.Lock()

    async def add(self, embeddings: np.ndarray, chunks: list):
        async with self._lock:
            faiss.normalize_L2(embeddings)
            if self._index is None:
                self._index = faiss.IndexFlatIP(embeddings.shape[1])
            self._index.add(embeddings)
            self._chunks.extend(chunks)
            self._save()
        logger.info(f"vector store: {self.total_chunks} total chunks")

    async def search(self, qvec: np.ndarray, k: int=None) -> list:
        if not self.is_ready: raise VectorStoreNotReadyError()
        s = get_settings()
        k = k or s.top_k_retrieval
        async with self._lock:
            faiss.normalize_L2(qvec)
            scores, idxs = self._index.search(qvec, k)
        out = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx==-1 or float(score)<s.min_relevance_score: continue
            c = self._chunks[idx]
            c.score = float(score)
            out.append(c)
        return out

    def load(self) -> bool:
        if not self._idx_path.exists(): return False
        try:
            self._index = faiss.read_index(str(self._idx_path))
            self._chunks = pickle.loads(self._meta_path.read_bytes())
            logger.info(f"vector store loaded: {len(self._chunks)} chunks")
            return True
        except Exception as e:
            logger.warning(f"vector store load failed: {e}")
            return False

    @property
    def is_ready(self): return self._index is not None and self._index.ntotal>0
    @property
    def total_chunks(self): return len(self._chunks)

    def _save(self):
        self._dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._idx_path))
        self._meta_path.write_bytes(pickle.dumps(self._chunks))

# Singleton instances
bm25_index = BM25Index()
vector_store = VectorStore()
