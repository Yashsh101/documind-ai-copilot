"""
DocuMind v3 — Intelligent Chunking Engine

Implements semantic-aware paragraph chunking with overlap and page tracking.
"""
import re
from typing import List, Dict, Any
from app.config import get_settings, logger

s = get_settings()


def chunk_text(text: str, document_id: str) -> List[Dict[str, Any]]:
    """
    Chunks document text using semantic paragraph boundaries with configurable
    size and overlap. Tracks page numbers via PAGE_N markers inserted during extraction.
    
    Strategy:
    1. Split on double newlines (paragraph boundaries)
    2. Accumulate paragraphs until chunk_size is reached
    3. Apply chunk_overlap by carrying trailing content to next chunk
    4. Track approximate page numbers from PAGE_N markers
    """
    paragraphs = re.split(r'\n{2,}', text)
    chunks: List[Dict[str, Any]] = []

    current_paragraphs: List[str] = []
    current_length = 0
    current_page = 1

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Extract page markers
        if "PAGE_" in para:
            try:
                current_page = int(para.split("PAGE_")[1].split()[0])
                para = re.sub(r'PAGE_\d+', '', para).strip()
                if not para:
                    continue
            except (ValueError, IndexError):
                pass

        current_paragraphs.append(para)
        current_length += len(para)

        if current_length >= s.chunk_size:
            chunk_text_val = " ".join(current_paragraphs)
            chunks.append({
                "document_id": document_id,
                "page": current_page,
                "text": chunk_text_val,
            })

            # Overlap: carry last paragraph(s) forward
            overlap_paras = []
            overlap_len = 0
            for p in reversed(current_paragraphs):
                if overlap_len + len(p) <= s.chunk_overlap:
                    overlap_paras.insert(0, p)
                    overlap_len += len(p)
                else:
                    break

            current_paragraphs = overlap_paras
            current_length = overlap_len

    # Flush remaining content
    if current_paragraphs:
        chunks.append({
            "document_id": document_id,
            "page": current_page,
            "text": " ".join(current_paragraphs),
        })

    logger.info(f"Chunked document {document_id}: {len(chunks)} chunks created")
    return chunks
