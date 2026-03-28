from __future__ import annotations
from openai import AsyncOpenAI
from app.config import get_settings
from app.utils.logger import logger

_P = """Rewrite this question to improve semantic retrieval. Be specific.
Output ONLY the rewritten query.
Question: {q}
Rewritten:"""

async def rewrite_query(query: str) -> str:
    s = get_settings()
    client = AsyncOpenAI(api_key=s.openai_api_key)
    try:
        r = await client.chat.completions.create(
            model=s.llm_model,
            messages=[{"role":"user","content":_P.format(q=query)}],
            temperature=0.0, max_tokens=100)
        rw = (r.choices[0].message.content or "").strip()
        if rw:
            logger.info(f"rewrite: '{query}' -> '{rw}'")
            return rw
    except Exception as e:
        logger.warning(f"rewrite failed: {e}")
    return query