import re
from dataclasses import dataclass

@dataclass
class Citation:
    chunk_id: int
    preview: str
    relevance_score: float

def extract_citations(answer: str, retrieved_chunks: list[dict]) -> list[Citation]:
    referenced_ids = {int(m) for m in re.findall(r"\[chunk_(\d+)\]", answer)}
    chunk_map = {c["chunk_id"]: c for c in retrieved_chunks}
    citations: list[Citation] = []
    for cid in sorted(referenced_ids):
        if cid in chunk_map:
            chunk = chunk_map[cid]
            citations.append(Citation(
                chunk_id=cid,
                preview=chunk["text"][:200].strip(),
                relevance_score=round(chunk.get("score", 0.0), 4),
            ))
    return citations

def clean_answer(answer: str) -> str:
    return re.sub(r"\s*\[chunk_\d+\]", "", answer).strip()