from __future__ import annotations
from openai import AsyncOpenAI, APIError
from app.config import get_settings
from app.services.ingestion import Chunk
from app.utils.exceptions import LLMError
from app.utils.logger import logger

_SYSTEM_PROMPT = """You are a precise, helpful customer support AI.
Rules you MUST follow:
1. Answer ONLY from the provided context chunks.
2. If the context does not contain enough information, say exactly:
   "I don't have enough information in the provided documents to answer this."
3. Cite every chunk you draw from using [chunk_N] notation inline.
4. Never fabricate facts, URLs, or statistics.
5. Be concise — avoid padding or filler sentences."""

async def generate_answer(query: str, retrieved_chunks: list[Chunk], history: list[dict]) -> str:
    if not retrieved_chunks:
        return "I don't have enough information in the provided documents to answer this."
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    context_block = "\n\n".join(
        f"[chunk_{c.chunk_id}] (source: {c.source})\n{c.text}" for c in retrieved_chunks
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": f"Context:\n{context_block}\n\nQuestion: {query}"},
    ]
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    except APIError as exc:
        raise LLMError(f"LLM call failed: {exc}") from exc
    logger.info("llm_response", extra={
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
    })
    return response.choices[0].message.content or ""