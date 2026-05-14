import json
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.config import logger
from app.services.rag import (
    run_pipeline, stream_pipeline,
    OpenAIQuotaExceededException, OpenAIAPIError
)

router = APIRouter(prefix="/api/v1", tags=["chat"])


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    session_id: Optional[str] = "default"
    document_ids: Optional[List[str]] = []
    history: Optional[List[Dict[str, str]]] = []


class CitationItem(BaseModel):
    document_id: str
    page: int
    snippet: str
    relevance_score: Optional[float] = 0.0


class ActionItem(BaseModel):
    label: str
    type: str
    payload: str


class QueryResponse(BaseModel):
    answer: Optional[str]
    citations: List[CitationItem]
    status: str
    message: Optional[str] = None
    confidence_score: Optional[float] = 0.0
    suggested_actions: Optional[List[ActionItem]] = []
    latency_ms: Optional[float] = 0.0
    eval_metrics: Optional[Dict[str, Any]] = {}


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    logger.info(f"Query: {req.question[:80]}...")

    try:
        answer, citations, extras = run_pipeline(
            query=req.question,
            document_ids=req.document_ids,
            history=req.history,
            session_id=req.session_id,
        )

        return QueryResponse(
            answer=answer,
            citations=[
                CitationItem(
                    document_id=c["document_id"],
                    page=c["page"],
                    snippet=c["snippet"],
                    relevance_score=c.get("relevance_score", 0.0),
                )
                for c in citations
            ],
            status="success",
            confidence_score=extras.get("confidence_score", 0.0),
            suggested_actions=[
                ActionItem(**a) for a in extras.get("suggested_actions", [])
            ],
            latency_ms=extras.get("latency_ms", 0.0),
            eval_metrics=extras.get("eval_metrics", {}),
        )
    except OpenAIQuotaExceededException as e:
        logger.error(f"OpenAI quota exceeded: {e}")
        return JSONResponse(status_code=503, content={
            "answer": None, "citations": [], "status": "error",
            "message": str(e.user_facing_message),
            "error_type": "quota_exceeded", "confidence_score": 0.0,
            "suggested_actions": [], "latency_ms": 0.0,
        })
    except OpenAIAPIError as e:
        logger.error(f"OpenAI API error: {e}")
        return JSONResponse(status_code=503, content={
            "answer": None, "citations": [], "status": "error",
            "message": str(e.user_facing_message),
            "error_type": "api_error", "confidence_score": 0.0,
            "suggested_actions": [], "latency_ms": 0.0,
        })
    except Exception as e:
        logger.error(f"Query pipeline failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={
            "answer": None, "citations": [], "status": "error",
            "message": "Pipeline execution failed. Check backend logs.",
            "confidence_score": 0.0, "suggested_actions": [], "latency_ms": 0.0,
        })


@router.post("/chat/stream")
@router.post("/query/stream")
async def stream_chat_endpoint(req: QueryRequest):
    logger.info(f"Stream query: {req.question[:80]}...")

    async def event_generator():
        try:
            async for chunk in stream_pipeline(
                query=req.question,
                document_ids=req.document_ids,
                history=req.history,
                session_id=req.session_id,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except OpenAIQuotaExceededException as e:
            logger.error(f"Stream: OpenAI quota exceeded: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error_type': 'quota_exceeded', 'content': str(e.user_facing_message)})}\n\n"
        except OpenAIAPIError as e:
            logger.error(f"Stream: OpenAI API error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error_type': 'api_error', 'content': str(e.user_facing_message)})}\n\n"
        except Exception as e:
            logger.error(f"Stream pipeline failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Stream generation failed. Check backend logs.'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
