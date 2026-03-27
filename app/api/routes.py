from __future__ import annotations
import time
from fastapi import APIRouter, File, UploadFile, HTTPException
from app.api.schemas import (
    ChatHistoryResponse, HealthResponse, HistoryMessage,
    QueryRequest, QueryResponse, UploadResponse,
    CitationSchema, EvalMetricsSchema,
)
from app.config import get_settings
from app.rag.pipeline import run_query
from app.services.embedding import get_embeddings
from app.services.ingestion import ingest_pdf
from app.services.memory import add_turn, clear_session, get_history
from app.services.retrieval import vector_store
from app.utils.logger import logger

router = APIRouter()
settings = get_settings()

@router.post("/upload-documents", response_model=UploadResponse)
async def upload_documents(files: list[UploadFile] = File(...)):
    start = time.perf_counter()
    for f in files:
        if not (f.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=415, detail=f"'{f.filename}' is not a PDF.")
    all_chunks = []
    start_id = vector_store.total_chunks
    for upload in files:
        content = await upload.read()
        chunks = ingest_pdf(content, upload.filename or "unknown.pdf", start_id=start_id)