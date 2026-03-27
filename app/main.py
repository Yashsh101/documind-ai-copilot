from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.config import get_settings
from app.services.retrieval import vector_store
from app.utils.exceptions import register_exception_handlers
from app.utils.logger import RequestLoggingMiddleware, logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.vector_store_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
    loaded = vector_store.load()
    if loaded:
        logger.info("startup index restored")
    else:
        logger.info("startup no index found")
    yield
    logger.info("shutdown")

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description="Production-grade RAG-based AI customer support system.",
        lifespan=lifespan,
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router, prefix="/api/v1")
    register_exception_handlers(app)
    return app

app = create_app()
