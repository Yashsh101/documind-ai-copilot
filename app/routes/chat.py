import json
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.config import logger
from app.services.rag import run_pipeline, stream_pipeline, LLMError, LLMQuotaError

router = APIRouter(prefix="/api/v1", tags=["chat"])


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    session_id: Optional[str] = "default"
    history: Optional[List[Dict[str, str]]] = []


class CitationItem(BaseModel):
    document_id: str
    page: int
    snippet: str
    relevance_score: Optional[float] = 0.0


class QueryResponse(BaseModel):
    answer: Optional[str]
    citations: List[CitationItem]
    status: str
    message: Optional[str] = None
    confidence_score: Optional[float] = 0.0
    latency_ms: Optional[float] = 0.0
    eval_metrics: Optional[Dict[str, Any]] = {}


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    logger.info(f"Query: {req.question[:80]}...")
    try:
        answer, citations, extras = await run_pipeline(
            query=req.question, history=req.history, session_id=req.session_id,
        )
        return QueryResponse(
            answer=answer,
            citations=[CitationItem(**c) for c in citations],
            status="success",
            confidence_score=extras.get("confidence_score", 0.0),
            latency_ms=extras.get("latency_ms", 0.0),
            eval_metrics=extras.get("eval_metrics", {}),
        )
    except LLMQuotaError as e:
        return JSONResponse(status_code=429, content={
            "answer": None, "citations": [], "status": "error",
            "message": str(e), "error_type": "quota_exceeded",
            "confidence_score": 0.0, "latency_ms": 0.0,
        })
    except LLMError as e:
        return JSONResponse(status_code=503, content={
            "answer": None, "citations": [], "status": "error",
            "message": str(e), "error_type": "llm_error",
            "confidence_score": 0.0, "latency_ms": 0.0,
        })
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={
            "answer": None, "citations": [], "status": "error",
            "message": "Pipeline execution failed.", "confidence_score": 0.0, "latency_ms": 0.0,
        })


@router.post("/chat/stream")
async def stream_chat_endpoint(req: QueryRequest):
    logger.info(f"Stream: {req.question[:80]}...")

    async def event_generator():
        try:
            async for chunk in stream_pipeline(
                query=req.question, history=req.history, session_id=req.session_id,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            logger.error(f"Stream failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
