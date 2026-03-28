from __future__ import annotations
import asyncio
from openai import AsyncOpenAI
from app.config import get_settings
from app.utils.logger import logger

_RERANK_PROMPT = """\
Rate the relevance of this document passage to the user query.
Score from 0 to 10 (10 = perfectly answers the query, 0 = completely irrelevant).
Output ONLY a single integer score, nothing else.

Query: {query}
Passage: {passage}
Score:"""

async def rerank_chunks(query: str, chunks: list, top_k: int=5) -> list:
    """
    Re-score chunks using LLM relevance judgment.
    Falls back gracefully if API fails.
    """
    if not chunks: return []
    s = get_settings()
    if not s.reranking_enabled or len(chunks) <= top_k:
        return chunks[:top_k]

    client = AsyncOpenAI(api_key=s.openai_api_key)

    async def score_chunk(chunk, idx: int) -> tuple[int, float]:
        try:
            r = await client.chat.completions.create(
                model=s.llm_model,
                messages=[{"role":"user","content":_RERANK_PROMPT.format(
                    query=query, passage=chunk.text[:500])}],
                temperature=0.0, max_tokens=5)
            raw = r.choices[0].message.content.strip()
            score = float(raw.split()[0]) / 10.0
            return (idx, score)
        except Exception:
            return (idx, chunk.score)

    tasks = [score_chunk(c, i) for i, c in enumerate(chunks)]
    results = await asyncio.gather(*tasks)
    ranked = sorted(results, key=lambda x: x[1], reverse=True)
    reranked = [chunks[idx] for idx, score in ranked[:top_k]]
    for i, (idx, score) in enumerate(ranked[:top_k]):
        reranked[i].score = score

    logger.info(f"reranked {len(chunks)} -> {len(reranked)} chunks")
    return reranked
