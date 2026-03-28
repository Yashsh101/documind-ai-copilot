from __future__ import annotations
from dataclasses import dataclass, field
from app.rag.query_rewriter import rewrite_query
from app.services.embedding import get_query_embedding
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
    rewritten = await rewrite_query(query)
    qvec = await get_query_embedding(rewritten)
    chunks = await vector_store.search(qvec)
    logger.info(f"retrieved {len(chunks)} chunks")
    chunk_dicts = [{"chunk_id":c.chunk_id,"text":c.text,"source":c.source,"score":c.score} for c in chunks]
    raw = await generate_answer(query, chunks, history)
    citations = extract_citations(raw, chunk_dicts)
    answer = clean_answer(raw)
    metrics = evaluate(raw, chunk_dicts)
    return RAGResult(answer=answer, citations=citations,
        rewritten_query=rewritten, eval_metrics=metrics, retrieved_chunks=chunk_dicts)
