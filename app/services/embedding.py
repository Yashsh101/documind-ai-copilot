from __future__ import annotations
import asyncio, numpy as np
from openai import AsyncOpenAI, RateLimitError, APIError
from app.config import get_settings
from app.utils.exceptions import EmbeddingError
from app.utils.logger import logger

async def get_embeddings(texts: list[str]) -> np.ndarray:
    if not texts: raise EmbeddingError("Empty list.")
    s = get_settings()
    client = AsyncOpenAI(api_key=s.openai_api_key)
    result = []
    batches = [texts[i:i+100] for i in range(0,len(texts),100)]
    for i,batch in enumerate(batches):
        for attempt in range(1,4):
            try:
                r = await client.embeddings.create(model=s.embedding_model, input=batch)
                result.extend([e.embedding for e in r.data])
                logger.info(f"embedded batch {i+1}/{len(batches)}")
                break
            except RateLimitError: await asyncio.sleep(2**attempt)
            except APIError as e:
                if attempt==3: raise EmbeddingError(str(e)) from e
                await asyncio.sleep(2**attempt)
    return np.array(result, dtype="float32")

async def get_query_embedding(text: str) -> np.ndarray:
    return await get_embeddings([text])