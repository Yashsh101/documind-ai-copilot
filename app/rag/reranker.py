"""
DocuMind v3 — Cross-Encoder Reranker (Lightweight)

Reranks retrieved chunks using a lightweight LLM-based relevance scoring.
Falls back to original ranking if reranking fails.
"""
import json
import httpx
from typing import List, Dict, Any
from app.config import get_settings, logger

s = get_settings()

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

    for chunk in chunks[:top_k + 2]:  # Score a few extra for safety
        prompt = RERANK_PROMPT.format(query=query, text=chunk["text"][:500])
        payload = {
            "model": s.llm_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0, "num_predict": 30},
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(f"{s.ollama_base_url}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("response", "{}")
                parsed = json.loads(content)
                relevance = float(parsed.get("score", 0))
                chunk["rerank_score"] = relevance / 10.0  # Normalize to 0-1
                reranked.append(chunk)
        except Exception as e:
            logger.warning(f"Rerank failed for chunk: {e}")
            chunk["rerank_score"] = chunk.get("score", 0)
            reranked.append(chunk)

    reranked.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    final = reranked[:top_k]

    logger.info(f"Reranked {len(chunks)} → {len(final)} chunks")
    return final
