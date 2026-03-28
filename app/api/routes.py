from __future__ import annotations
import time
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.api.schemas import *
from app.config import get_settings
from app.core.pipeline import run_query, add_turn, clear_session, get_history
from app.core.embedding import get_embeddings
from app.core.ingestion import ingest_pdf
from app.core.retrieval import bm25_index, vector_store
from app.utils.logger import logger

router = APIRouter()

@router.post("/upload-documents", response_model=UploadResponse)
async def upload_documents(files: list[UploadFile] = File(...)):
    start = time.perf_counter()
    for f in files:
        if not (f.filename or "").lower().endswith(".pdf"):
            raise HTTPException(415, f"'{f.filename}' is not a PDF.")
    all_chunks = []
    sid = vector_store.total_chunks
    for upload in files:
        content = await upload.read()
        chunks = ingest_pdf(content, upload.filename or "file.pdf", start_id=sid)
        sid += len(chunks)
        all_chunks.extend(chunks)
    if not all_chunks:
        raise HTTPException(422, "No text extracted.")

    embeddings = await get_embeddings([c.text for c in all_chunks])
    await vector_store.add(embeddings, all_chunks)
    bm25_index.build(all_chunks)

    latency = round((time.perf_counter()-start)*1000, 1)
    logger.info(f"indexed {len(all_chunks)} chunks in {latency}ms")
    return UploadResponse(status="indexed", files_processed=len(files),
        chunks_stored=len(all_chunks), total_chunks=vector_store.total_chunks,
        latency_ms=latency)

@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    start = time.perf_counter()
    history = get_history(req.session_id)
    result = await run_query(req.question, history)
    add_turn(req.session_id, req.question, result.answer)
    latency = round((time.perf_counter()-start)*1000, 1)
    return QueryResponse(
        answer=result.answer,
        citations=[CitationOut(chunk_id=c.chunk_id, preview=c.preview,
            relevance_score=c.relevance_score, source=c.source)
            for c in result.citations],
        rewritten_query=result.rewritten_query,
        eval_metrics=MetricsOut(context_recall=result.eval_metrics.context_recall,
            answer_faithfulness=result.eval_metrics.answer_faithfulness,
            avg_relevance_score=result.eval_metrics.avg_relevance_score),
        confidence=ConfidenceOut(score=result.confidence.score,
            label=result.confidence.label,
            should_escalate=result.confidence.should_escalate,
            reason=result.confidence.reason),
        actions=result.actions,
        session_id=req.session_id, latency_ms=latency)

@router.get("/chat-history/{session_id}", response_model=ChatHistoryResponse)
async def chat_history(session_id: str):
    h = get_history(session_id)
    return ChatHistoryResponse(session_id=session_id, turns=len(h)//2,
        history=[HistoryMessage(role=m["role"],content=m["content"]) for m in h])

@router.delete("/chat-history/{session_id}")
async def clear_history(session_id: str):
    clear_session(session_id)
    return {"status":"cleared","session_id":session_id}

@router.get("/health", response_model=HealthResponse)
async def health():
    s = get_settings()
    return HealthResponse(status="ok", index_ready=vector_store.is_ready,
        total_chunks=vector_store.total_chunks, version=s.api_version,
        model=s.llm_model,
        features={"hyde": s.hyde_enabled, "hybrid_search": s.hybrid_search_enabled,
                  "reranking": s.reranking_enabled})