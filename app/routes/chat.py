"""
DocuMind v3 — Chat Routes (Standard + Streaming)
"""
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from app.config import logger
from app.models.schemas import QueryRequest, QueryResponse, CitationItem, ActionItem
from app.rag.pipeline import run_pipeline, stream_pipeline

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    """Standard (non-streaming) query endpoint."""
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
        )
    except Exception as e:
        logger.error(f"Query pipeline failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={
            "answer": None,
            "citations": [],
            "status": "error",
            "message": "Pipeline execution failed. Check backend logs.",
            "confidence_score": 0.0,
            "suggested_actions": [],
            "latency_ms": 0.0,
        })


@router.post("/chat/stream")
async def stream_chat_endpoint(req: QueryRequest):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).
    Streams tokens as they are generated, followed by metadata.
    """
    logger.info(f"Stream query: {req.question[:80]}...")

    async def event_generator():
        try:
            for chunk in stream_pipeline(
                query=req.question,
                document_ids=req.document_ids,
                history=req.history,
                session_id=req.session_id,
            ):
                event_data = json.dumps(chunk)
                yield f"data: {event_data}\n\n"
        except Exception as e:
            logger.error(f"Stream pipeline failed: {e}", exc_info=True)
            error_event = json.dumps({
                "type": "error",
                "content": "Stream generation failed. Check backend logs."
            })
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
