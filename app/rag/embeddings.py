"""
DocuMind v3 — Embedding Service

Generates dense vector embeddings via Ollama with in-memory caching.
"""
import httpx
from typing import List
from app.config import get_settings, logger
from app.core.cache import embedding_cache

s = get_settings()

_EMBEDDING_DIM = 4096  # Llama 3 embedding dimension
_ZERO_VECTOR = [0.0] * _EMBEDDING_DIM


def get_query_embedding(text: str) -> List[float]:
    """
    Get embedding for a single query text. Uses TTL cache to avoid
    redundant Ollama API calls.
    """
    if not text or not text.strip():
        return _ZERO_VECTOR

    # Check cache first
    cached = embedding_cache.get(text)
    if cached is not None:
        return cached

    url = f"{s.ollama_base_url}/api/embeddings"
    payload = {"model": s.llm_model, "prompt": text}

    for attempt in range(2):
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                embedding = data.get("embedding", _ZERO_VECTOR)
                embedding_cache.set(text, embedding)
                return embedding
        except httpx.TimeoutException:
            logger.warning(f"Embedding timeout attempt {attempt + 1}")
        except httpx.RequestError as e:
            logger.error(f"Embedding connection error: {e}")
        except Exception as e:
            logger.error(f"Embedding failed attempt {attempt + 1}: {e}")

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
