"""
DocuMind v3 — PDF Ingestion Engine

Handles PDF parsing, text extraction, chunking, embedding, and storage.
"""
import os
import uuid
import json
import fitz  # PyMuPDF
from typing import List
from app.config import get_settings, logger
from app.rag.chunking import chunk_text
from app.rag.embeddings import get_document_embeddings

s = get_settings()


def ingest_pdf(file_bytes: bytes, filename: str) -> tuple[str, int]:
    """
    Full ingestion pipeline:
    1. Extract text from PDF with page markers
    2. Chunk text with overlap
    3. Generate embeddings for each chunk
    4. Store as JSON for retrieval
    
    Returns: (document_id, chunk_count)
    """
    doc_id = str(uuid.uuid4())[:8] + "_" + filename.replace(" ", "_").lower().replace(".pdf", "")

    # === Step 1: Extract text from PDF ===
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        full_text_parts: List[str] = []
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                full_text_parts.append(f"\nPAGE_{i + 1}\n{text}")
        doc.close()
    except Exception as e:
        logger.error(f"PDF extraction failed for {filename}: {e}")
        raise ValueError(f"Invalid PDF structure: {e}")

    raw_text = "\n".join(full_text_parts)
    if not raw_text.strip():
        raise ValueError("No extractable text found in PDF")

    # === Step 2: Chunk the text ===
    chunks = chunk_text(raw_text, doc_id)
    if not chunks:
        raise ValueError("Chunking produced zero chunks")

    # === Step 3: Generate embeddings ===
    texts_to_embed = [c["text"] for c in chunks]
    embeddings = get_document_embeddings(texts_to_embed)

    for i, chunk in enumerate(chunks):
        chunk["embedding"] = embeddings[i]

    # === Step 4: Persist to disk ===
    os.makedirs(s.data_dir, exist_ok=True)
    store_path = os.path.join(s.data_dir, f"{doc_id}.json")
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f)

    logger.info(f"Ingested '{filename}' → {doc_id} ({len(chunks)} chunks)")
    return doc_id, len(chunks)


def load_all_chunks(allowed_docs: List[str] = None) -> List[dict]:
    """Load all document chunks from disk, optionally filtering by document IDs."""
    all_chunks = []
    if not os.path.exists(s.data_dir):
        return all_chunks

    for fname in os.listdir(s.data_dir):
        if not fname.endswith(".json"):
            continue
        doc_id = fname.replace(".json", "")
        if allowed_docs and doc_id not in allowed_docs:
            continue
        try:
            with open(os.path.join(s.data_dir, fname), "r", encoding="utf-8") as f:
                all_chunks.extend(json.load(f))
        except Exception as e:
            logger.error(f"Failed to load {fname}: {e}")

    return all_chunks


def get_indexed_document_count() -> int:
    """Count the number of indexed document files."""
    if not os.path.exists(s.data_dir):
        return 0
    return len([f for f in os.listdir(s.data_dir) if f.endswith(".json")])
