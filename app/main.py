"""
DocuMind v3 — FastAPI Application Entry Point

Production-grade AI Customer Support Copilot.
"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings, logger
from app.routes import health, documents, chat

s = get_settings()

# Ensure data directory exists
Path(s.data_dir).mkdir(parents=True, exist_ok=True)

# === App Initialization ===
app = FastAPI(
    title=s.api_title,
    version=s.api_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Register Routers ===
app.include_router(health.router)
app.include_router(documents.router)
app.include_router(chat.router)


# === Global Exception Handler ===
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={
        "answer": None,
        "citations": [],
        "status": "error",
        "message": "An unexpected system error occurred.",
        "confidence_score": 0.0,
        "suggested_actions": [],
    })


# === Startup Event ===
@app.on_event("startup")
async def startup_event():
    logger.info(f"DocuMind v{s.api_version} starting...")
    logger.info(f"LLM Model: {s.openai_chat_model}")
    logger.info(f"Embedding Model: {s.openai_embedding_model}")
    logger.info(f"Data directory: {s.data_dir}")
    logger.info(f"Hybrid search weights: BM25={s.bm25_weight}, Vector={s.vector_weight}")
    logger.info(f"Reranking: {'enabled' if s.rerank_enabled else 'disabled'}")


# === Static Files & SPA Serving ===
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def serve_spa():
    return FileResponse("app/static/index.html")
