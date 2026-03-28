from __future__ import annotations
import asyncio, pickle
from pathlib import Path
import faiss, numpy as np
from app.config import get_settings
from app.utils.exceptions import VectorStoreNotReadyError
from app.utils.logger import logger

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
        logger.info(f"store total {self.total_chunks} chunks")

    async def search(self, qvec: np.ndarray, k=None) -> list:
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
            logger.info(f"loaded {len(self._chunks)} chunks")
            return True
        except Exception as e:
            logger.warning(f"load failed: {e}")
            return False

    @property
    def is_ready(self): return self._index is not None and self._index.ntotal>0
    @property
    def total_chunks(self): return len(self._chunks)

    def _save(self):
        self._dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._idx_path))
        self._meta_path.write_bytes(pickle.dumps(self._chunks))

vector_store = VectorStore()
