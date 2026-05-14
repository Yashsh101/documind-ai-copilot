from typing import List, Optional
from openai import OpenAI, RateLimitError, APIError
from app.config import get_settings, logger
from app.services.rag import TTLCache, OpenAIQuotaExceededException, OpenAIAPIError

s = get_settings()
embedding_cache = TTLCache(max_size=2000, ttl_seconds=7200)
_EMBEDDING_DIM_CACHE = None


def _get_openai_client() -> Optional[OpenAI]:
    api_key = s.openai_api_key
    if not api_key:
        return None
    if s.openai_base_url:
        return OpenAI(api_key=api_key, base_url=s.openai_base_url)
    return OpenAI(api_key=api_key)


def _get_embedding_dim() -> int:
    global _EMBEDDING_DIM_CACHE
    if _EMBEDDING_DIM_CACHE is not None:
        return _EMBEDDING_DIM_CACHE
    if s.openai_embedding_model == "nomic-embed-text":
        _EMBEDDING_DIM_CACHE = 768
    else:
        _EMBEDDING_DIM_CACHE = 1536
    return _EMBEDDING_DIM_CACHE


def _get_zero_vector() -> list:
    return [0.0] * _get_embedding_dim()


def get_query_embedding(text: str) -> List[float]:
    if not text or not text.strip():
        return _get_zero_vector()

    cached = embedding_cache.get(text)
    if cached is not None:
        return cached

    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; returning zero embedding.")
        return _get_zero_vector()

    try:
        response = client.embeddings.create(
            model=s.openai_embedding_model,
            input=text,
        )
        embedding = response.data[0].embedding if response.data else _get_zero_vector()
        embedding_cache.set(text, embedding)
        return embedding
    except RateLimitError as exc:
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
    embeddings = []
    for i, text in enumerate(texts):
        emb = get_query_embedding(text)
        embeddings.append(emb)
        if (i + 1) % 10 == 0:
            logger.info(f"Embedded {i + 1}/{len(texts)} chunks")
    return embeddings
