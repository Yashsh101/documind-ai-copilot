import os
import re
import json
import uuid
from typing import Tuple, List, Dict, Any
import fitz  # PyMuPDF
from app.config import get_settings, logger
from app.core.embedding import get_document_embeddings, get_query_embedding

s = get_settings()

def chunk_text(text: str, document_id: str) -> List[Dict[str, Any]]:
    """
    Splits text into sliding chunks.
    Maintains page references by splitting roughly.
    """
    # Simple semantic fallback chunking without LangChain dependency
    paragraphs = re.split(r'\n{2,}', text)
    chunks = []
    
    current_chunk = []
    current_length = 0
    page_approx = 1
    
    for p in paragraphs:
        p = p.strip()
        if not p: continue
        
        # very rough heuristic for page markers
        if "PAGE_" in p:
            try:
                page_approx = int(p.split("PAGE_")[1].split()[0])
                # Remove the page marker so we keep the text
                p = re.sub(r'PAGE_\d+', '', p).strip()
                if not p: continue
            except: pass
            
        current_chunk.append(p)
        current_length += len(p)
        
        if current_length > s.chunk_size:
            text_val = " ".join(current_chunk)
            chunks.append({
                "document_id": document_id,
                "page": page_approx,
                "text": text_val
            })
            # Overlap: keep the last paragraph
            current_chunk = [p]
            current_length = len(p)
            
    if current_chunk:
        chunks.append({
            "document_id": document_id,
            "page": page_approx,
            "text": " ".join(current_chunk)
        })
        
    return chunks

def ingest_pdf(file_bytes: bytes, filename: str) -> str:
    """
    Parses a PDF from bytes, chunks it, stub-embeds it, and saves it to data/
    """
    doc_id = str(uuid.uuid4())[:8] + "_" + filename.replace(" ", "_").lower()
    
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        full_text = []
        for i, page in enumerate(doc):
            t = page.get_text("text").strip()
            if t:
                # Insert our page marker heuristic
                full_text.append(f"\nPAGE_{i+1}\n" + t)
        doc.close()
    except Exception as e:
        logger.error(f"Failed to extract PDF text: {e}")
        raise ValueError("Invalid PDF structure")
        
    raw_text = "\n".join(full_text)
    if not raw_text.strip():
        raise ValueError("No text found in PDF")
        
    chunks = chunk_text(raw_text, doc_id)
    
    # Compute embeddings stub
    texts_to_embed = [c["text"] for c in chunks]
    embeddings = get_document_embeddings(texts_to_embed)
    
    for i, c in enumerate(chunks):
        c["embedding"] = embeddings[i]
        
    # Persist to disk
    store_path = os.path.join(s.data_dir, f"{doc_id}.json")
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f)
        
    return doc_id

def _load_all_chunks(allowed_docs: List[str] = None) -> List[Dict[str, Any]]:
    all_chunks = []
    for fname in os.listdir(s.data_dir):
        if not fname.endswith(".json"): continue
        
        doc_id = fname.replace(".json", "")
        if allowed_docs and doc_id not in allowed_docs: continue
        
        with open(os.path.join(s.data_dir, fname), "r", encoding="utf-8") as f:
            all_chunks.extend(json.load(f))
    return all_chunks

def tfidf_score(query: str, text: str) -> float:
    """
    Simple keyword intersection (BM25 surrogate) for the pure Python pipeline.
    More effective than comparing random hash dense vectors.
    """
    q_words = set(re.findall(r'\w+', query.lower()))
    t_words = re.findall(r'\w+', text.lower())
    match_count = sum(1 for w in t_words if w in q_words)
    return match_count / (len(t_words) + 1.0) * 100.0

def run_query(query: str, document_ids: List[str] = None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Executes a RAG retrieval and generation stub.
    """
    chunks = _load_all_chunks(document_ids)
    if not chunks:
        raise ValueError("No matching documents indexed.")
        
    # 1. Embed query (Cached via lru_cache in embedding.py)
    # Stub: calling it just to prove the pipeline triggers it correctly
    _ = get_query_embedding(query)
    
    # 2. Retrieve (using keyword scoring since dense vector is a random hash stub)
    for c in chunks:
        c["score"] = tfidf_score(query, c["text"])
        
    chunks.sort(key=lambda x: x["score"], reverse=True)
    top_chunks = chunks[:s.top_k_retrieval]
    
    if not top_chunks or top_chunks[0]["score"] == 0:
        return "I could not find a relevant answer in the uploaded documents.", []
        
    # 3. Generation Engine (Extractive approach for now, ready for LLMs)
    # Extracting the most relevant snippet and formatting as the answer.
    best_chunk = top_chunks[0]
    generated_answer = (
        f"Based on the knowledge base documents, here is the relevant information: \n\n"
        f"\"{best_chunk['text'][:400]}...\"\n\n"
        f"*(This is an extractive answer computed strictly in Python. Plug in an LLM call here to synthesize text natively!)*"
    )
    
    # Format citations dynamically from source materials safely
    citations = []
    for c in top_chunks:
        if c["score"] > 0:
            citations.append({
                "document_id": c["document_id"],
                "page": c["page"],
                "snippet": c["text"][:150] + "..."
            })
            
    return generated_answer, citations
