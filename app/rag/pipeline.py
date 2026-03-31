"""
DocuMind v3 — Full RAG Pipeline Orchestrator

Orchestrates the complete query pipeline:
Query → Rewrite → Retrieve (Hybrid) → Rerank → Generate → Actions
"""
import time
from typing import List, Dict, Any, Tuple, Optional
from app.config import get_settings, logger
from app.core.cache import query_cache
from app.rag.ingestion import load_all_chunks
from app.rag.retriever import hybrid_search
from app.rag.reranker import rerank_chunks
from app.services.llm import generate_answer, rewrite_query
from app.services.suggestions import generate_actions
from app.services.memory import MemoryManager
from app.core.prompts import SYSTEM_PROMPT

s = get_settings()


def run_pipeline(
    query: str,
    document_ids: List[str] = None,
    history: List[Dict[str, str]] = None,
    session_id: str = "default",
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Full RAG pipeline execution:
    
    1. Query Rewriting (context-aware)
    2. Memory injection (conversation context)
    3. Hybrid retrieval (BM25 + vector)
    4. Reranking (LLM-based)
    5. Answer generation
    6. Action suggestion generation
    7. Memory update
    
    Returns: (answer, citations, extras)
    """
    pipeline_start = time.time()
    memory = MemoryManager(session_id)

    # === Step 0: Check cache ===
    cache_key = f"{query}:{','.join(document_ids or [])}"
    cached = query_cache.get(cache_key)
    if cached:
        logger.info("Cache hit for query")
        return cached

    # === Step 1: Query Rewriting ===
    rewrite_start = time.time()
    if history and len(history) > 1:
        rewritten_query = rewrite_query(query, history)
        logger.info(f"Query rewritten: '{query}' → '{rewritten_query}' ({time.time() - rewrite_start:.2f}s)")
    else:
        rewritten_query = query

    # === Step 2: Load document chunks ===
    chunks = load_all_chunks(document_ids if document_ids else None)

    if not chunks:
        # No documents — use no-context fallback
        answer = generate_answer(query, "", history, no_context=True)
        actions, conf = generate_actions(query, answer)
        result = (answer, [], {
            "confidence_score": conf,
            "suggested_actions": actions,
            "latency_ms": round((time.time() - pipeline_start) * 1000, 1),
        })
        return result

    # === Step 3: Hybrid Retrieval ===
    retrieval_start = time.time()
    retrieved = hybrid_search(rewritten_query, chunks, top_k=s.top_k_retrieval + 3)
    logger.info(f"Retrieval: {len(retrieved)} chunks in {time.time() - retrieval_start:.2f}s")

    # === Step 4: Reranking ===
    rerank_start = time.time()
    if s.rerank_enabled and len(retrieved) > 2:
        top_chunks = rerank_chunks(rewritten_query, retrieved, top_k=s.top_k_retrieval)
    else:
        top_chunks = retrieved[:s.top_k_retrieval]
    logger.info(f"Reranking: {len(top_chunks)} final chunks in {time.time() - rerank_start:.2f}s")

    # === Step 5: Build context ===
    context_text = "\n\n---\n\n".join([
        f"[Source: {c['document_id']} | Page {c['page']}]\n{c['text']}"
        for c in top_chunks
    ])

    # Inject memory context
    memory_context = memory.get_context_string()
    if memory_context:
        context_text = f"## Previous Conversation Context\n{memory_context}\n\n## Document Context\n{context_text}"

    # === Step 6: Answer Generation ===
    gen_start = time.time()
    answer = generate_answer(query, context_text, history)
    logger.info(f"Answer generation: {time.time() - gen_start:.2f}s")

    # === Step 7: Action Suggestions ===
    action_start = time.time()
    actions, confidence = generate_actions(query, answer)
    logger.info(f"Action generation: {time.time() - action_start:.2f}s")

    # === Step 8: Build citations ===
    citations = []
    for c in top_chunks:
        score = c.get("rerank_score", c.get("score", 0))
        if score > s.min_relevance_score:
            citations.append({
                "document_id": c["document_id"],
                "page": c["page"],
                "snippet": c["text"][:200] + "...",
                "relevance_score": round(score, 3),
            })

    # === Step 9: Update memory ===
    memory.add_turn(query, answer)

    # === Finalize ===
    total_latency = round((time.time() - pipeline_start) * 1000, 1)
    logger.info(f"Pipeline complete: {total_latency}ms total latency")

    extras = {
        "confidence_score": confidence,
        "suggested_actions": actions,
        "latency_ms": total_latency,
        "eval_metrics": {
            "retrieved_chunks": len(top_chunks),
            "citation_count": len(citations),
            "rerank_enabled": s.rerank_enabled,
        },
    }

    result = (answer, citations, extras)
    query_cache.set(cache_key, result)

    return result


def stream_pipeline(
    query: str,
    document_ids: List[str] = None,
    history: List[Dict[str, str]] = None,
    session_id: str = "default",
):
    """
    Streaming version of the pipeline. Yields SSE-compatible chunks.
    Uses the same retrieval pipeline but streams the LLM response.
    """
    from app.services.llm import stream_answer

    pipeline_start = time.time()
    memory = MemoryManager(session_id)

    # Query rewriting
    if history and len(history) > 1:
        rewritten_query = rewrite_query(query, history)
    else:
        rewritten_query = query

    # Load and search
    chunks = load_all_chunks(document_ids if document_ids else None)

    if not chunks:
        context_text = ""
        no_context = True
    else:
        retrieved = hybrid_search(rewritten_query, chunks, top_k=s.top_k_retrieval + 3)

        if s.rerank_enabled and len(retrieved) > 2:
            top_chunks = rerank_chunks(rewritten_query, retrieved, top_k=s.top_k_retrieval)
        else:
            top_chunks = retrieved[:s.top_k_retrieval]

        context_text = "\n\n---\n\n".join([
            f"[Source: {c['document_id']} | Page {c['page']}]\n{c['text']}"
            for c in top_chunks
        ])

        memory_context = memory.get_context_string()
        if memory_context:
            context_text = f"## Previous Conversation Context\n{memory_context}\n\n## Document Context\n{context_text}"
        no_context = False

    # Stream tokens
    full_answer = ""
    for token in stream_answer(query, context_text, history, no_context=no_context):
        full_answer += token
        yield {"type": "token", "content": token}

    # After streaming, generate metadata
    actions, confidence = generate_actions(query, full_answer)

    # Citations
    citations = []
    if chunks and not no_context:
        for c in top_chunks:
            score = c.get("rerank_score", c.get("score", 0))
            if score > s.min_relevance_score:
                citations.append({
                    "document_id": c["document_id"],
                    "page": c["page"],
                    "snippet": c["text"][:200] + "...",
                    "relevance_score": round(score, 3),
                })

    memory.add_turn(query, full_answer)
    total_latency = round((time.time() - pipeline_start) * 1000, 1)

    yield {
        "type": "metadata",
        "data": {
            "citations": citations,
            "confidence_score": confidence,
            "suggested_actions": actions,
            "latency_ms": total_latency,
        }
    }

    yield {"type": "done"}
