from __future__ import annotations
import re
from dataclasses import dataclass, field

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
        answer_faithfulness=round(faith,3),
        avg_relevance_score=round(avg,4),
        details={"cited":sorted(cited),"retrieved":sorted(all_ids)})