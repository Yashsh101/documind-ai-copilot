from __future__ import annotations
import re
from dataclasses import dataclass, field
import fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import get_settings
from app.utils.exceptions import DocumentProcessingError
from app.utils.logger import logger

@dataclass
class Chunk:
    chunk_id: int
    text: str
    source: str = ""
    score: float = 0.0
    metadata: dict = field(default_factory=dict)

def extract_text_from_pdf(file_bytes: bytes, filename: str = "unknown.pdf") -> str:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise DocumentProcessingError(f"Cannot open PDF '{filename}': {exc}") from exc
    pages = [page.get_text("text") for page in doc if page.get_text("text").strip()]
    doc.close()
    if not pages:
        raise DocumentProcessingError(f"No extractable text found in '{filename}'.")
    return _clean_text("\n\n".join(pages))

def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"-\n(\w)", r"\1", text)
    return text.strip()

def chunk_text(text: str, source: str = "", start_id: int = 0) -> list[Chunk]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = []
    for i, raw in enumerate(splitter.split_text(text)):
        cleaned = raw.strip()
        if len(cleaned) < 30:
            continue
        chunks.append(Chunk(
            chunk_id=start_id + i,
            text=cleaned,
            source=source,
            metadata={"source": source, "chunk_index": i},
        ))
    logger.info("chunked_document", extra={"source": source, "chunks": len(chunks)})
    return chunks

def ingest_pdf(file_bytes: bytes, filename: str, start_id: int = 0) -> list[Chunk]:
    text = extract_text_from_pdf(file_bytes, filename)
    return chunk_text(text, source=filename, start_id=start_id)