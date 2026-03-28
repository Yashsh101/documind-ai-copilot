import json, logging, time, uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_RESERVED = {
    "args","created","exc_info","exc_text","filename","funcName",
    "levelname","levelno","lineno","message","module","msecs","msg",
    "name","pathname","process","processName","relativeCreated",
    "stack_info","thread","threadName","taskName",
}

class _JSONFormatter(logging.Formatter):
    def format(self, record):
        p = {"ts": self.formatTime(record,"%Y-%m-%dT%H:%M:%S"),
             "level": record.levelname, "message": record.getMessage()}
        if record.exc_info:
            p["exc"] = self.formatException(record.exc_info)
        for k,v in record.__dict__.items():
            if k not in _RESERVED:
                p[k] = v
        return json.dumps(p, default=str)

def _make_logger(name):
    log = logging.getLogger(name)
    if log.handlers: return log
    h = logging.StreamHandler()
    h.setFormatter(_JSONFormatter())
    log.addHandler(h)
    log.setLevel(logging.INFO)
    log.propagate = False
    return log

logger = _make_logger("copilot")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rid = str(uuid.uuid4())[:8]
        t0 = time.perf_counter()
        response = await call_next(request)
        ms = round((time.perf_counter()-t0)*1000,1)
        logger.info(f"[{request.method}] {request.url.path} {response.status_code} {ms}ms rid={rid}")
        response.headers["X-Request-Id"] = rid
        response.headers["X-Latency-Ms"] = str(ms)
        return response