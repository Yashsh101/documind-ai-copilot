import json
import logging
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

def _build_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    handler.setFormatter(_JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger

class _JSONFormatter(logging.Formatter):
    SKIP = {
        "args","created","exc_info","exc_text","filename","funcName",
        "levelname","levelno","lineno","message","module","msecs",
        "msg","name","pathname","process","processName",
        "relativeCreated","stack_info","thread","threadName","taskName",
    }
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for k, v in record.__dict__.items():
            if k not in self.SKIP:
                payload[k] = v
        return json.dumps(payload, default=str)

logger = _build_logger("copilot")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Latency-Ms"] = str(latency_ms)
        return response