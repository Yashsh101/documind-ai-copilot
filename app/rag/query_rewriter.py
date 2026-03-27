from __future__ import annotations
from openai import AsyncOpenAI
from app.config import get_settings
from app.utils.logger import logger

_REWRITE_PROMPT = """You are a search query optimiser for a document retrieval system.
Rewrite the user's question to maximise semantic search recall.
Output ONLY the rewritten query — no explanation.

Original question: {query}
Rewritten query:"""

async def rewrite_query(query: str) -> str:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": _REWRITE_PROMPT.format(query=query)}],
            temperature=0.0,
            max_tokens=120,
        )
        rewritten = response.choices[0].message.content.strip()
        logger.info("query_rewritten", extra={"original": query, "rewritten": rewritten})
        return rewritten or query
    except Exception as exc:
        logger.warning("query_rewrite_failed", extra={"error": str(exc)})
        return query