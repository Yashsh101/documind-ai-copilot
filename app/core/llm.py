from __future__ import annotations
from openai import AsyncOpenAI, APIError
from app.config import get_settings
from app.utils.helpers import LLMError
from app.utils.logger import logger

_SYS = """\
You are DocuMind, a precise AI customer support assistant.

RULES \u2014 follow every one without exception:
1. Answer ONLY from the provided context chunks.
2. If context is insufficient, say exactly:
   "I don't have enough information in the uploaded documents to answer this."
3. Cite every chunk you use with [chunk_N] inline.
4. Never invent facts, URLs, names, or statistics.
5. Structure your answer clearly. Use bullet points when listing steps.
6. Be concise but complete. Do not pad your answer.
"""

async def generate_answer(query: str, chunks: list, history: list[dict]) -> str:
    if not chunks:
        return "I don't have enough information in the uploaded documents to answer this."
    s = get_settings()
    client = AsyncOpenAI(api_key=s.openai_api_key)
    ctx = "\n\n".join(f"[chunk_{c.chunk_id}] source={c.source}\n{c.text}" for c in chunks)
    msgs = [{"role":"system","content":_SYS}, *history,
            {"role":"user","content":f"Context:\n{ctx}\n\nQuestion: {query}"}]
    try:
        r = await client.chat.completions.create(
            model=s.llm_model, messages=msgs,
            temperature=s.llm_temperature, max_tokens=s.llm_max_tokens)
    except APIError as e: raise LLMError(str(e)) from e
    logger.info(f"LLM tokens: prompt={r.usage.prompt_tokens} completion={r.usage.completion_tokens}")
    return r.choices[0].message.content or ""
