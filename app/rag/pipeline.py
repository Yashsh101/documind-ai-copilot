"""
RAG pipeline orchestrator.

This is the single entry point for the query flow:
  rewrite → embed → retrieve → generate → cite → evaluate

Keeping orchestration here (not in the API routes) means:
  - Routes stay thin (HTTP concerns only)
  - Pipeline is independently testable
  - Easy to swap any step (e.g. add a reranker between retrieve and generate)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.rag.query_rewriter import rewrite_query
from app.services.embedding import get_query_embedding
from app.services.ingestion import Chunk
from app.services.llm import generate_answer
from app.services.retrieval import vector_store
from app.utils.citations import Citation, clean_answer, extract_citations
from app.utils.evaluator import EvalResult, evaluate
from app.utils.logger import logger


@dataclass
class RAGResult:
    answer: str
    citations: list[Citation]
    rewritten_query: str
    eval_metrics: EvalResult
    retrieved_chunks: list[dict] = field(default_factory=list)


async def run_query(query: str, history: list[dict]) -> RAGResult:
    """
    Full RAG pipeline: query → answer with citations and eval metrics.
    """
    # Step 1: Rewrite query for better retrieval
    rewritten = await rewrite_query(query)

    # Step 2: Embed the rewritten query
    query_embedding = await get_query_embedding(rewritten)

    # Step 3: Semantic retrieval from FAISS
    chunks: list[Chunk] = await vector_store.search(query_embedding)

    logger.info(
        "retrieval_done",
        extra={"query": rewritten, "chunks_retrieved": len(chunks)},
    )

    # Step 4: LLM generation with grounded prompt + conversation history
    raw_answer = await generate_answer(query, chunks, history)

    # Step 5: Extract structured citations from [chunk_N] tags
    chunk_dicts = [
        {"chunk_id": c.chunk_id, "text": c.text, "source": c.source, "score": c.score}
        for c in chunks
    ]
    citations = extract_citations(raw_answer, chunk_dicts)
    clean = clean_answer(raw_answer)

    # Step 6: Evaluate quality inline
    metrics = evaluate(raw_answer, chunk_dicts)

    logger.info(
        "pipeline_complete",
        extra={
            "faithfulness": metrics.answer_faithfulness,
            "context_recall": metrics.context_recall,
        },
    )

    return RAGResult(
        answer=clean,
        citations=citations,
        rewritten_query=rewritten,
        eval_metrics=metrics,
        retrieved_chunks=chunk_dicts,
    )
