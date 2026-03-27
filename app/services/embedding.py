from __future__ import annotations
import asyncio
import numpy as np
from openai import AsyncOpenAI, RateLimitError, APIError
from app.config import get_settings
from app.utils.exceptions import EmbeddingError
from app.utils.logger import logger

_BATCH_SIZE = 100
_MAX_RETRIES = 3

async def get_embeddings(texts: list[str]) -> np.ndarray:
    if not texts:
        raise EmbeddingError("Cannot embed an empty text list.")
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    all_embeddings: list[list[float]] = []
    batches = [texts[i:i + _BATCH_SIZE] for i in range(0, len(texts), _BATCH_SIZE)]
    for batch_idx, batch in enumerate(batches):
        embeddings = await _embed_with_retry(client, batch, settings.embedding_model)
        all_embeddings.extend(embeddings)
        logger.info("embedding_batch_done", extra={"batch": batch_idx + 1, "total": len(batches)})
    return np.array(all_embeddings, dtype="float32")

async def get_query_embedding(text: str) -> np.ndarray:
    return await get_embeddings([text])

async def _embed_with_retry(client, texts, model):
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await client.embeddings.create(model=model, input=texts)
            return [item.embedding for item in response.data]
        except RateLimitError:
            await asyncio.sleep(2 ** attempt)
        except APIError as exc:
            if attempt == _MAX_RETRIES:
                raise EmbeddingError(f"OpenAI API error: {exc}") from exc
            await asyncio.sleep(2 ** attempt)
    raise EmbeddingError("Embedding failed after all retries.")