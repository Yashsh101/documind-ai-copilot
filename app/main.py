import uuid
import time
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings, logger
from app.core.pipeline import ingest_pdf, run_query

s = get_settings()
Path(s.data_dir).mkdir(parents=True, exist_ok=True)

app = FastAPI(title=s.api_title, version=s.api_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Schemas ---
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    session_id: Optional[str] = "default"
    document_ids: Optional[List[str]] = []

class CitationItem(BaseModel):
    document_id: str
    page: int
    snippet: str

class QueryResponse(BaseModel):
    answer: Optional[str]
    citations: List[CitationItem]
    status: str
    message: Optional[str] = None

# --- Exception Handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={
        "answer": None,
        "citations": [],
        "status": "error",
        "message": "An unexpected system failure occurred."
    })

# --- Routes ---
@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "version": s.api_version}

@app.post("/api/v1/upload")
async def upload_document(files: List[UploadFile] = File(...)):
    doc_ids = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            continue
        try:
            content = await f.read()
            doc_id = ingest_pdf(content, f.filename)
            doc_ids.append(doc_id)
            logger.info(f"Ingested {f.filename} successfully as {doc_id}.")
        except Exception as e:
            logger.error(f"Failed to process {f.filename}: {e}")
            return JSONResponse(status_code=422, content={"status": "error", "message": f"Failed to parse {f.filename}"})
            
    return {"status": "success", "document_ids": doc_ids, "message": "Documents processed successfully."}

@app.post("/api/v1/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    logger.info(f"Received query: {req.question}")
    try:
        ans, cites = run_query(req.question, req.document_ids)
        return QueryResponse(
            answer=ans,
            citations=[CitationItem(document_id=c["document_id"], page=c["page"], snippet=c["snippet"]) for c in cites],
            status="success"
        )
    except Exception as e:
        logger.error(f"Query pipeline failed: {e}")
        return JSONResponse(status_code=200, content={
            "answer": None,
            "citations": [],
            "status": "error",
            "message": "Retrieval or processing failed. Please check backend logs."
        })

# --- UI Serving ---
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def serve_spa():
    return FileResponse("app/static/index.html")
