import hashlib
from functools import lru_cache
from typing import List
from app.config import get_settings

# Grab cache size from settings
CACHE_SIZE = get_settings().embedding_cache_size

@lru_cache(maxsize=CACHE_SIZE)
def get_query_embedding(text: str) -> List[float]:
    """
    Computes a deterministic dummy 'embedding' for a query.
    Architected to be hot-swapped with actual OpenAI/Vertex AI calls.
    Uses lru_cache to prevent repetitive API operations.
    """
    if not text.strip():
        return [0.0] * 384
        
    # Generate a deterministic pseudo-random vector based on text hash
    h = hashlib.sha256(text.encode("utf-8")).digest()
    
    # Create a 384-dimensional dense vector stub using the hash bytes
    # Normalization or semantic meaning isn't present in this stub.
    vec = [(float(b) / 255.0) - 0.5 for b in h]
    # Pad or tile to 384 dims
    while len(vec) < 384:
        vec.extend(vec)
    
    return vec[:384]

def get_document_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Batch computes embeddings for chunked document texts.
    (Stub implementation)
    """
    return [get_query_embedding(t) for t in texts]
