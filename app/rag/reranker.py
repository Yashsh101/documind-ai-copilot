"""
DocuMind v3 — Cross-Encoder Reranker (Lightweight)

Reranks retrieved chunks using a lightweight OpenAI relevance scoring.
Falls back to original ranking if reranking fails.
"""
import json
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.config import get_settings, logger

s = get_settings()


def _get_openai_client() -> Optional[OpenAI]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

RERANK_PROMPT = """Rate the relevance of the following document excerpt to the query on a scale of 0 to 10.
Output ONLY a JSON object: {{"score": <number>}}

Query: {query}

Document Excerpt:
{text}

Relevance JSON:"""


def rerank_chunks(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = None,
) -> List[Dict[str, Any]]:
    """
    Reranks chunks using lightweight LLM scoring.
    
    Each chunk gets a relevance score from the LLM. Results are re-sorted
    by this score. Falls back to original ordering on failure.
    """
    if not s.rerank_enabled or not chunks:
        return chunks

    top_k = top_k or s.top_k_retrieval
    reranked = []

    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; skipping rerank.")
        for chunk in chunks[: top_k]:
            chunk["rerank_score"] = chunk.get("score", 0)
            reranked.append(chunk)
        reranked.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        final = reranked[:top_k]
        logger.info(f"Reranked {len(chunks)} → {len(final)} chunks")
        return final

    for chunk in chunks[: top_k + 2]:
        prompt = RERANK_PROMPT.format(query=query, text=chunk["text"][:500])
        messages = [
            {"role": "system", "content": "Score the relevance of a document excerpt to the query."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = client.chat.completions.create(
                model=s.openai_chat_model,
                messages=messages,
                temperature=0.0,
                max_tokens=32,
            )
            content = response.choices[0].message["content"].strip()
            parsed = json.loads(content)
            relevance = float(parsed.get("score", 0))
            chunk["rerank_score"] = relevance / 10.0
        except Exception as exc:
            logger.warning(f"Rerank failed for chunk: {exc}")
            chunk["rerank_score"] = chunk.get("score", 0)

        reranked.append(chunk)

    reranked.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    final = reranked[:top_k]

    logger.info(f"Reranked {len(chunks)} → {len(final)} chunks")
    return final
