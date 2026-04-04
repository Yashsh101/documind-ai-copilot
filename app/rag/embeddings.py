"""
DocuMind v3 — Embedding Service

Generates dense vector embeddings via OpenAI with in-memory caching.
"""
import os
from typing import List, Optional
from openai import OpenAI, RateLimitError, APIError
from app.config import get_settings, logger
from app.core.cache import embedding_cache

"""
DocuMind v3 — Embedding Service

Generates dense vector embeddings via OpenAI with in-memory caching.
"""
import os
from typing import List, Optional
from openai import OpenAI, RateLimitError, APIError
from app.config import get_settings, logger
from app.core.cache import embedding_cache
from app.core.exceptions import OpenAIQuotaExceededException, OpenAIAPIError

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
    
    Raises:
        OpenAIQuotaExceededException: If OpenAI quota is exceeded
        OpenAIAPIError: If OpenAI API call fails
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
    except RateLimitError as exc:
        # Check if this is an insufficient_quota error
        error_msg = str(exc)
        if "insufficient_quota" in error_msg.lower():
            logger.error(f"OpenAI quota exceeded: {exc}")
            raise OpenAIQuotaExceededException()
        else:
            logger.error(f"OpenAI rate limit: {exc}")
            raise OpenAIAPIError("OpenAI API rate limit exceeded. Please try again in a moment.")
    except APIError as exc:
        logger.error(f"OpenAI API error: {exc}")
        raise OpenAIAPIError(f"OpenAI API error: {str(exc)[:100]}")
    except Exception as exc:
        logger.error(f"Embedding generation failed: {exc}", exc_info=True)
        raise OpenAIAPIError()



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
