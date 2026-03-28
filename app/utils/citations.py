import re
from dataclasses import dataclass

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