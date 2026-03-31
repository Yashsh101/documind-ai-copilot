"""
DocuMind v3 — Embedding Service

Generates dense vector embeddings via OpenAI with in-memory caching.
"""
import os
from typing import List, Optional
from openai import OpenAI
from app.config import get_settings, logger
from app.core.cache import embedding_cache

s = get_settings()


def _get_openai_client() -> Optional[OpenAI]:
    api_key = s.openai_api_key
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

_EMBEDDING_DIM = 1536
_ZERO_VECTOR = [0.0] * _EMBEDDING_DIM


def get_query_embedding(text: str) -> List[float]:
    """
    Get embedding for a single query text. Uses TTL cache to avoid
    redundant OpenAI API calls.
    """
    if not text or not text.strip():
        return _ZERO_VECTOR

    cached = embedding_cache.get(text)
    if cached is not None:
        return cached

    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; returning zero embedding.")
        return _ZERO_VECTOR

    try:
        response = client.embeddings.create(
            model=s.openai_embedding_model,
            input=text,
        )
        embedding = response.data[0].embedding if response.data else _ZERO_VECTOR
        embedding_cache.set(text, embedding)
        return embedding
    except Exception as exc:
        logger.error(f"OpenAI embedding failed: {exc}", exc_info=True)
        return _ZERO_VECTOR


def get_document_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Batch compute embeddings for document chunks.
    Sequential for fault tolerance — each chunk gets its own retry cycle.
    """
    embeddings = []
    for i, text in enumerate(texts):
        emb = get_query_embedding(text)
        embeddings.append(emb)
        if (i + 1) % 10 == 0:
            logger.info(f"Embedded {i + 1}/{len(texts)} chunks")
    return embeddings
