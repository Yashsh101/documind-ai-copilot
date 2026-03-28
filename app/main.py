from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.api.routes import router
from app.config import get_settings
from app.core.retrieval import vector_store, bm25_index
from app.utils.helpers import register_exception_handlers
from app.utils.logger import RequestLoggingMiddleware, logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    Path(s.vector_store_dir).mkdir(parents=True, exist_ok=True)
    Path(s.uploads_dir).mkdir(parents=True, exist_ok=True)
    vec_loaded = vector_store.load()
    bm25_index.load()
    if vec_loaded:
        logger.info(f"startup: restored {vector_store.total_chunks} chunks")
    else:
        logger.info("startup: no index found, ready for uploads")
    logger.info(f"DocuMind v2 features: HyDE=on hybrid=on reranking=on")
    yield
    logger.info("server shutdown")

def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.api_title, version=s.api_version,
        description="DocuMind v2 — Production RAG with HyDE + hybrid retrieval + reranking",
        lifespan=lifespan)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=s.allowed_origins,
        allow_methods=["*"], allow_headers=["*"])
    app.include_router(router, prefix="/api/v1")
    register_exception_handlers(app)
    @app.get("/")
    async def ui(): return FileResponse("index.html")
    return app

app = create_app()
