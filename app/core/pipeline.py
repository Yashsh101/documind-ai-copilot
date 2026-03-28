from __future__ import annotations
import asyncio
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field

from openai import AsyncOpenAI
from app.config import get_settings
from app.core.embedding import get_query_embedding
from app.core.retrieval import vector_store, bm25_index
from app.core.reranker import rerank_chunks
from app.core.action_engine import suggest_actions
from app.core.llm import generate_answer
from app.utils.helpers import Citation, clean_answer, extract_citations, EvalResult, evaluate, ConfidenceResult, score_confidence
from app.utils.logger import logger

# --- Memory ---
_store: dict[str,deque] = defaultdict(
    lambda: deque(maxlen=get_settings().max_history_turns*2))

def get_history(sid: str) -> list[dict]: return list(_store[sid])
def add_turn(sid: str, user: str, asst: str):
    _store[sid].append({"role":"user","content":user})
    _store[sid].append({"role":"assistant","content":asst})
def clear_session(sid: str): _store.pop(sid, None)

# --- Query Rewriter ---
_REWRITE_PROMPT = """Rewrite this customer support question to improve semantic retrieval.
Make it specific, remove vague pronouns, expand abbreviations.
Output ONLY the rewritten query.
Question: {q}
Rewritten:"""

async def rewrite_query(query: str) -> str:
    s = get_settings()
    client = AsyncOpenAI(api_key=s.openai_api_key)
    try:
        r = await client.chat.completions.create(
            model=s.llm_model,
            messages=[{"role":"user","content":_REWRITE_PROMPT.format(q=query)}],
            temperature=0.0, max_tokens=100)
        rw = (r.choices[0].message.content or "").strip()
        if rw:
            logger.info(f"query rewrite: '{query}' -> '{rw}'")
            return rw
    except Exception as e:
        logger.warning(f"rewrite failed: {e}")
    return query

# --- HyDE ---
_HYDE_PROMPT = """\
Generate a short hypothetical document that would perfectly answer this question.
Write it as if it were a real excerpt from a knowledge base article.
Be specific and factual. 2-3 sentences maximum.

Question: {query}
Hypothetical document:"""

async def generate_hypothetical_document(query: str) -> str:
    s = get_settings()
    if not s.hyde_enabled:
        return query
    client = AsyncOpenAI(api_key=s.openai_api_key)
    try:
        r = await client.chat.completions.create(
            model=s.llm_model,
            messages=[{"role":"user","content":_HYDE_PROMPT.format(query=query)}],
            temperature=0.3, max_tokens=150)
        hyp = (r.choices[0].message.content or "").strip()
        if hyp:
            logger.info(f"HyDE generated hypothetical doc for: '{query}'")
            return hyp
    except Exception as e:
        logger.warning(f"HyDE failed, using original query: {e}")
    return query

# --- Context Compressor ---
def compress_chunks(chunks: list, query: str, max_chars: int = 3000) -> list:
    query_words = set(re.findall(r"\w+", query.lower()))
    compressed = []
    total_chars = 0

    for chunk in chunks:
        sentences = re.split(r"(?<=[.!?])\s+", chunk.text)
        scored = []
        for sent in sentences:
            if len(sent.strip()) < 15:
                continue
            words = set(re.findall(r"\w+", sent.lower()))
            overlap = len(words & query_words) / max(len(words), 1)
            scored.append((overlap, sent))
        scored.sort(reverse=True)
        kept = " ".join(s for _, s in scored[:5])
        if not kept.strip():
            kept = chunk.text[:500]
        chunk.text = kept
        total_chars += len(kept)
        compressed.append(chunk)
        if total_chars >= max_chars:
            break

    logger.info(f"compressed context to {total_chars} chars from {len(chunks)} chunks")
    return compressed

# --- Pipeline ---
@dataclass
class RAGResult:
    answer: str
    citations: list[Citation]
    rewritten_query: str
    eval_metrics: EvalResult
    confidence: ConfidenceResult
    actions: list[str] = field(default_factory=list)
    retrieved_chunks: list[dict] = field(default_factory=list)
    pipeline_steps: list[str] = field(default_factory=list)

async def run_query(query: str, history: list[dict]) -> RAGResult:
    s = get_settings()
    steps = []

    rewritten = await rewrite_query(query)
    steps.append(f"rewrite: '{query}' -> '{rewritten}'")

    hyde_doc = await generate_hypothetical_document(rewritten)
    embed_text = hyde_doc if s.hyde_enabled else rewritten
    steps.append("hyde: generated hypothetical document")

    qvec = await get_query_embedding(embed_text)
    dense_chunks = await vector_store.search(qvec, k=s.top_k_retrieval)
    steps.append(f"dense retrieval: {len(dense_chunks)} chunks")

    sparse_results = []
    if s.hybrid_search_enabled:
        sparse_results = bm25_index.search(rewritten, k=s.top_k_retrieval)
        steps.append(f"sparse BM25: {len(sparse_results)} chunks")

    seen_ids = {c.chunk_id for c in dense_chunks}
    merged = list(dense_chunks)
    for chunk, bm25_score in sparse_results:
        if chunk.chunk_id not in seen_ids:
            chunk.score = bm25_score * 0.3
            merged.append(chunk)
            seen_ids.add(chunk.chunk_id)
    steps.append(f"merged: {len(merged)} unique chunks")

    reranked = await rerank_chunks(rewritten, merged, top_k=s.top_k_rerank)
    steps.append(f"reranked: {len(reranked)} final chunks")

    compressed = compress_chunks(reranked, rewritten)
    steps.append("context compressed")

    raw_answer = await generate_answer(query, compressed, history)

    chunk_dicts = [{"chunk_id":c.chunk_id,"text":c.text,
        "source":c.source,"score":c.score} for c in compressed]
    citations = extract_citations(raw_answer, chunk_dicts)
    answer = clean_answer(raw_answer)

    metrics = evaluate(raw_answer, chunk_dicts)

    confidence = score_confidence(
        avg_relevance=metrics.avg_relevance_score,
        context_recall=metrics.context_recall,
        faithfulness=metrics.answer_faithfulness,
        num_citations=len(citations),
        num_chunks=len(compressed),
    )

    actions = await suggest_actions(query, answer)

    logger.info(f"pipeline complete: faith={metrics.answer_faithfulness} confidence={confidence.label}")

    return RAGResult(answer=answer, citations=citations,
        rewritten_query=rewritten, eval_metrics=metrics,
        confidence=confidence, actions=actions, retrieved_chunks=chunk_dicts,
        pipeline_steps=steps)
