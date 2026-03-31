"""
DocuMind v3 — Pydantic Request/Response Schemas
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# === Request Schemas ===

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    session_id: Optional[str] = "default"
    document_ids: Optional[List[str]] = []
    history: Optional[List[Dict[str, str]]] = []


# === Response Schemas ===

class CitationItem(BaseModel):
    document_id: str
    page: int
    snippet: str
    relevance_score: Optional[float] = 0.0


class ActionItem(BaseModel):
    label: str
    type: str  # "query" | "action"
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


class StreamChunk(BaseModel):
    """Schema for SSE streaming chunks."""
    type: str  # "token" | "citations" | "actions" | "done" | "error"
    content: Optional[str] = None
    data: Optional[dict] = None


class UploadResponse(BaseModel):
    status: str
    document_ids: List[str]
    message: str
    chunk_count: Optional[int] = 0


class HealthResponse(BaseModel):
    status: str
    version: str
    provider: Optional[str] = "openai"
    indexed_documents: Optional[int] = 0
