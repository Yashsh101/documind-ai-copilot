from __future__ import annotations
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    session_id: str = Field(default="default", max_length=64)

class CitationSchema(BaseModel):
    chunk_id: int
    preview: str
    relevance_score: float

class EvalMetricsSchema(BaseModel):
    context_recall: float
    answer_faithfulness: float
    avg_relevance_score: float

class UploadResponse(BaseModel):
    status: str
    files_processed: int
    chunks_stored: int
    latency_ms: float

class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationSchema]
    rewritten_query: str
    eval_metrics: EvalMetricsSchema
    session_id: str
    latency_ms: float

class HistoryMessage(BaseModel):
    role: str
    content: str

class ChatHistoryResponse(BaseModel):
    session_id: str
    turns: int
    history: list[HistoryMessage]

class HealthResponse(BaseModel):
    status: str
    index_ready: bool
    total_chunks: int
    version: str