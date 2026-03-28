from __future__ import annotations
import re
from dataclasses import dataclass, field
import fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import get_settings
from app.utils.helpers import DocumentProcessingError
from app.utils.logger import logger

@dataclass
class Chunk:
    chunk_id: int
    text: str
    source: str = ""
    score: float = 0.0
    metadata: dict = field(default_factory=dict)

def extract_text(file_bytes: bytes, filename: str) -> str:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise DocumentProcessingError(f"Cannot open {filename}: {e}") from e
    pages = [p.get_text("text") for p in doc if p.get_text("text").strip()]
    doc.close()
    if not pages: raise DocumentProcessingError(f"No text in {filename}.")
    raw = "\n\n".join(pages)
    raw = re.sub(r"\n{3,}","\n\n",raw)
    raw = re.sub(r"[ \t]+"," ",raw)
    raw = re.sub(r"-\n(\w)",r"\1",raw)
    return raw.strip()

def chunk_text(text: str, source: str="", start_id: int=0) -> list[Chunk]:
    s = get_settings()
    sp = RecursiveCharacterTextSplitter(
        chunk_size=s.chunk_size, chunk_overlap=s.chunk_overlap,
        separators=["\n\n","\n",". "," ",""])
    chunks = []
    for i,raw in enumerate(sp.split_text(text)):
        t = raw.strip()
        if len(t) < 30: continue
        chunks.append(Chunk(chunk_id=start_id+i, text=t, source=source,
            metadata={"source":source,"index":i,"char_count":len(t)}))
    logger.info(f"chunked {source} into {len(chunks)} chunks")
    return chunks

def ingest_pdf(file_bytes: bytes, filename: str, start_id: int=0) -> list[Chunk]:
    return chunk_text(extract_text(file_bytes, filename),
        source=filename, start_id=start_id)
