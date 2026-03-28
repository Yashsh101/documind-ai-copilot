from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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
        logger.info("startup complete — index restored from disk")
    else:
        logger.info("startup complete — no index found, ready for uploads")
    yield
    logger.info("server shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description="Production-grade RAG AI customer support system.",
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes first
    app.include_router(router, prefix="/api/v1")
    register_exception_handlers(app)

    # Serve index.html at root
    @app.get("/")
    async def serve_ui():
        return FileResponse("index.html")

    # Serve any other static assets
    if Path("static").exists():
        app.mount("/static", StaticFiles(directory="static"), name="static")

    return app


app = create_app()