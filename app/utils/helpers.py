import re
from dataclasses import dataclass, field
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# --- Exceptions ---

class CopilotError(Exception):
    status_code: int = 500
    detail: str = "An unexpected error occurred."
    def __init__(self, detail=None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)

class DocumentProcessingError(CopilotError):
    status_code = 422; detail = "Failed to process document."

class VectorStoreNotReadyError(CopilotError):
    status_code = 503; detail = "No documents indexed. Upload PDFs first."

class EmbeddingError(CopilotError):
    status_code = 502; detail = "Embedding API call failed."

class LLMError(CopilotError):
    status_code = 502; detail = "LLM API call failed."

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(CopilotError)
    async def handle(request: Request, exc: CopilotError):
        return JSONResponse(status_code=exc.status_code,
            content={"error": exc.__class__.__name__, "detail": exc.detail})
    @app.exception_handler(Exception)
    async def handle_generic(request: Request, exc: Exception):
        return JSONResponse(status_code=500,
            content={"error": "InternalServerError", "detail": "Something went wrong."})

# --- Citations ---

@dataclass
class Citation:
    chunk_id: int
    preview: str
    relevance_score: float
    source: str = ""

def extract_citations(answer: str, chunks: list[dict]) -> list[Citation]:
    ids = {int(m) for m in re.findall(r"\[chunk_(\d+)\]", answer)}
    m = {c["chunk_id"]: c for c in chunks}
    return [Citation(chunk_id=i, preview=m[i]["text"][:200].strip(),
            relevance_score=round(m[i].get("score",0.0),4),
            source=m[i].get("source",""))
            for i in sorted(ids) if i in m]

def clean_answer(answer: str) -> str:
    return re.sub(r"\s*\[chunk_\d+\]", "", answer).strip()

# --- Confidence Scoring ---

@dataclass
class ConfidenceResult:
    score: float
    label: str
    should_escalate: bool
    reason: str

def score_confidence(
    avg_relevance: float,
    context_recall: float,
    faithfulness: float,
    num_citations: int,
    num_chunks: int,
) -> ConfidenceResult:
    if num_chunks == 0:
        return ConfidenceResult(0.0, "low", True, "No relevant documents found")

    retrieval_score = (avg_relevance * 0.5) + (context_recall * 0.5)
    generation_score = (faithfulness * 0.7) + (min(num_citations, 3) / 3 * 0.3)
    composite = (retrieval_score * 0.4) + (generation_score * 0.6)

    if composite >= 0.70:
        return ConfidenceResult(
            score=round(composite, 3), label="high",
            should_escalate=False, reason="Strong retrieval and grounded answer")
    elif composite >= 0.45:
        return ConfidenceResult(
            score=round(composite, 3), label="medium",
            should_escalate=False, reason="Moderate confidence \u2014 verify with sources")
    else:
        return ConfidenceResult(
            score=round(composite, 3), label="low",
            should_escalate=True, reason="Low confidence \u2014 recommend human review")

# --- Evaluator ---

@dataclass
class EvalResult:
    context_recall: float = 0.0
    answer_faithfulness: float = 0.0
    avg_relevance_score: float = 0.0
    details: dict = field(default_factory=dict)

def evaluate(answer: str, chunks: list[dict]) -> EvalResult:
    if not chunks: return EvalResult()
    cited = {int(m) for m in re.findall(r"\[chunk_(\d+)\]", answer)}
    all_ids = {c["chunk_id"] for c in chunks}
    recall = len(cited & all_ids)/len(all_ids) if all_ids else 0.0
    ctx = set(re.findall(r"\w+", " ".join(c["text"] for c in chunks).lower()))
    ans = {w for w in re.findall(r"\w+", answer.lower()) if len(w)>3}
    faith = len(ans & ctx)/len(ans) if ans else 0.0
    avg = sum(c.get("score",0.0) for c in chunks)/len(chunks)
    return EvalResult(context_recall=round(recall,3),
        answer_faithfulness=round(faith,3), avg_relevance_score=round(avg,4),
        details={"cited":sorted(cited),"retrieved":sorted(all_ids)})
