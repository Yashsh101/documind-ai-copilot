from __future__ import annotations
import re
from dataclasses import dataclass, field

@dataclass
class EvalResult:
    context_recall: float = 0.0
    answer_faithfulness: float = 0.0
    avg_relevance_score: float = 0.0
    details: dict = field(default_factory=dict)

def evaluate(answer: str, retrieved_chunks: list[dict]) -> EvalResult:
    if not retrieved_chunks:
        return EvalResult()
    cited_ids = {int(m) for m in re.findall(r"\[chunk_(\d+)\]", answer)}
    all_ids = {c["chunk_id"] for c in retrieved_chunks}
    context_recall = len(cited_ids & all_ids) / len(all_ids) if all_ids else 0.0
    context_text = " ".join(c["text"] for c in retrieved_chunks).lower()
    context_words = set(re.findall(r"\w+", context_text))
    answer_words = set(re.findall(r"\w+", answer.lower()))
    meaningful = {w for w in answer_words if len(w) > 3}
    faithfulness = len(meaningful & context_words) / len(meaningful) if meaningful else 0.0
    scores = [c.get("score", 0.0) for c in retrieved_chunks]
    avg_score = sum(scores) / len(scores)
    return EvalResult(
        context_recall=round(context_recall, 3),
        answer_faithfulness=round(faithfulness, 3),
        avg_relevance_score=round(avg_score, 4),
        details={"cited_chunk_ids": sorted(cited_ids), "retrieved_chunk_ids": sorted(all_ids)},
    )