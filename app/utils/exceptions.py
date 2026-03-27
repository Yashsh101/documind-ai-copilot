from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

class CopilotError(Exception):
    status_code: int = 500
    detail: str = "An unexpected error occurred."
    def __init__(self, detail: str | None = None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)

class DocumentProcessingError(CopilotError):
    status_code = 422
    detail = "Failed to process document."

class VectorStoreNotReadyError(CopilotError):
    status_code = 503
    detail = "Vector store not initialised. Upload documents first."

class EmbeddingError(CopilotError):
    status_code = 502
    detail = "Embedding API call failed."

class LLMError(CopilotError):
    status_code = 502
    detail = "LLM API call failed."

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CopilotError)
    async def copilot_error_handler(request: Request, exc: CopilotError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.__class__.__name__, "detail": exc.detail},
        )
    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": "InternalServerError", "detail": "An unexpected error occurred."},
        )