"""
DocuMind v3 — Hybrid Retriever (BM25 + Vector Search)

Combines sparse (BM25) and dense (cosine similarity) retrieval for
superior recall and precision. Weighted fusion produces final ranked results.
"""
import re
import numpy as np
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
from app.config import get_settings, logger
from app.rag.embeddings import get_query_embedding

s = get_settings()


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + lowercase tokenizer for BM25."""
    return re.findall(r'\w+', text.lower())


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a, b = np.array(v1, dtype=np.float32), np.array(v2, dtype=np.float32)
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def hybrid_search(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = None,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval combining BM25 (sparse) + vector cosine (dense).
    
    Pipeline:
    1. BM25 scoring on tokenized chunk texts
    2. Cosine similarity on dense embeddings
    3. Min-max normalization of both score sets
    4. Weighted fusion: final = bm25_weight * bm25 + vector_weight * cosine
    5. Return top-k ranked results
    """
    if not chunks:
        return []

    top_k = top_k or s.top_k_retrieval

    # === BM25 Sparse Retrieval ===
    corpus_tokens = [_tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(corpus_tokens)
    query_tokens = _tokenize(query)
    bm25_scores = bm25.get_scores(query_tokens)

    # === Dense Vector Retrieval ===
    query_embedding = get_query_embedding(query)
    vector_scores = np.array([
        cosine_similarity(query_embedding, c.get("embedding", [0.0] * len(query_embedding)))
        for c in chunks
    ], dtype=np.float32)

    # === Min-Max Normalization ===
    def normalize(scores: np.ndarray) -> np.ndarray:
        min_s, max_s = scores.min(), scores.max()
        if max_s - min_s == 0:
            return np.zeros_like(scores)
        return (scores - min_s) / (max_s - min_s)

    bm25_norm = normalize(np.array(bm25_scores, dtype=np.float32))
    vector_norm = normalize(vector_scores)

    # === Weighted Fusion ===
    fusion_scores = (s.bm25_weight * bm25_norm) + (s.vector_weight * vector_norm)

    # === Rank and return top-k ===
    scored_chunks = []
    for i, chunk in enumerate(chunks):
        scored_chunks.append({
            **chunk,
            "score": float(fusion_scores[i]),
            "bm25_score": float(bm25_norm[i]),
            "vector_score": float(vector_norm[i]),
        })

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    top_results = scored_chunks[:top_k]

    logger.info(
        f"Hybrid search: {len(chunks)} chunks → top-{top_k} "
        f"(best score: {top_results[0]['score']:.3f})" if top_results else "no results"
    )

    return top_results
