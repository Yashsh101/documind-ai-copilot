import os, re, json, time, uuid, hashlib
from typing import List, Dict, Any, Optional, Tuple
from collections import OrderedDict, defaultdict
import numpy as np
from rank_bm25 import BM25Okapi
import fitz
from openai import OpenAI, RateLimitError, APIError
from app.config import get_settings, logger

s = get_settings()

# ═══════════════════════════════════════════════════
# 1. TTL Cache
# ═══════════════════════════════════════════════════

class TTLCache:
    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def get(self, key: str) -> Optional[Any]:
        hashed = self._hash_key(key)
        if hashed in self._cache:
            value, timestamp = self._cache[hashed]
            if time.time() - timestamp < self._ttl:
                self._cache.move_to_end(hashed)
                self._hits += 1
                return value
            else:
                del self._cache[hashed]
        self._misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        hashed = self._hash_key(key)
        if hashed in self._cache:
            del self._cache[hashed]
        self._cache[hashed] = (value, time.time())
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def invalidate(self, key: str) -> None:
        hashed = self._hash_key(key)
        if hashed in self._cache:
            del self._cache[hashed]

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{(self._hits / total * 100):.1f}%" if total > 0 else "0%",
        }


query_cache = TTLCache(max_size=200, ttl_seconds=300)
llm_cache = TTLCache(max_size=100, ttl_seconds=600)

# ═══════════════════════════════════════════════════
# 2. Exceptions
# ═══════════════════════════════════════════════════

class DocuMindException(Exception):
    pass


class OpenAIQuotaExceededException(DocuMindException):
    def __init__(self, message: str = None):
        if message is None:
            message = "OpenAI API quota exceeded. Please check your billing and add credits at https://platform.openai.com/account/billing/overview"
        super().__init__(message)
        self.user_facing_message = message


class OpenAIAPIError(DocuMindException):
    def __init__(self, message: str = None):
        if message is None:
            message = "OpenAI API error. Please try again or contact support."
        super().__init__(message)
        self.user_facing_message = message


class PipelineException(DocuMindException):
    def __init__(self, message: str = None):
        if message is None:
            message = "Pipeline execution failed. Please try again."
        super().__init__(message)
        self.user_facing_message = message


# ═══════════════════════════════════════════════════
# 3. Prompts
# ═══════════════════════════════════════════════════

SYSTEM_PROMPT = """You are DocuMind, an elite AI Customer Support Copilot built for enterprise teams.

## Your Core Principles
- You solve problems DIRECTLY. Never deflect with "contact support" or "I cannot help."
- You are precise, structured, and human. Never robotic.
- You cite specific document sections when available.
- You anticipate what the user needs next.

## Response Structure (Always Follow)
1. **Direct Answer** — Lead with the solution. No preamble.
2. **Explanation** — Provide context only when it adds value.
3. **Action Steps** — Numbered steps if the solution requires actions.
4. **Edge Cases** — Mention relevant caveats or exceptions.

## Formatting Rules
- Use **bold** for key terms and actions
- Use bullet points for lists
- Use numbered steps for procedures
- Keep paragraphs short (2-3 sentences max)
- Never use unnecessary filler phrases

## Tone
Professional but warm. Think senior support engineer at a top SaaS company — knowledgeable, efficient, empathetic."""

RAG_PROMPT_TEMPLATE = """{system_prompt}

## Retrieved Knowledge Base Context
The following excerpts were retrieved from the company's documentation. Use them to ground your answer.
If the context doesn't contain relevant information, say so honestly rather than fabricating.

---
{context}
---

## Conversation History (Recent)
{history}

## Current Question
{query}

## Instructions
- Answer using ONLY the provided context when possible
- If context is insufficient, clearly state what you know and what you don't
- Structure your response using the formatting rules above
- Be specific — reference document sections, page numbers, or policy details
- Do NOT repeat the question back"""

QUERY_REWRITE_PROMPT = """Given the conversation history and current question, rewrite the question to be self-contained and optimized for document retrieval.

Rules:
- Resolve all pronouns and references using conversation context
- Keep the rewritten query concise (under 50 words)
- Preserve the user's original intent exactly
- Output ONLY the rewritten query, nothing else

Conversation History:
{history}

Current Question: {query}

Rewritten Query:"""

ACTION_SUGGESTION_PROMPT = """You are a classification and action-generation engine for a customer support system.

Based on the user's question and the answer provided, generate a JSON object with:
1. A confidence score (0-100) measuring how completely the answer addresses the question
2. Up to 3 highly specific, contextual follow-up actions

Requirements:
- Actions must be SPECIFIC to this conversation (never generic)
- Each action is either a "query" (follow-up question) or "action" (concrete step)
- Labels should be concise (under 10 words)
- Payloads for queries should be full, self-contained questions

Output strictly valid JSON. No markdown code blocks.

{{
  "confidence_score": <float 0-100>,
  "actions": [
    {{"label": "...", "type": "query", "payload": "..."}},
    {{"label": "...", "type": "action", "payload": "..."}}
  ]
}}

User Question: {query}
Answer Given: {answer}

Return the JSON object:"""

HYDE_PROMPT = """Write a short, factual paragraph that would appear in a company's customer support documentation to answer this question. Write as if you are the documentation author. Keep it under 100 words.

Question: {query}

Documentation Excerpt:"""

NO_CONTEXT_PROMPT = """{system_prompt}

The knowledge base is currently empty — no documents have been uploaded yet.

The user asked: {query}

Respond helpfully:
1. Acknowledge you don't have company-specific documents to reference
2. Provide any general guidance you can based on the question
3. Suggest the user upload relevant documents for accurate, source-grounded answers
4. Be concise and professional"""

# ═══════════════════════════════════════════════════
# 4. Memory
# ═══════════════════════════════════════════════════

_session_memory: Dict[str, List[Dict]] = defaultdict(list)


class MemoryManager:
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.window_size = s.memory_window_size

    @property
    def turns(self) -> List[Dict]:
        return _session_memory[self.session_id]

    def add_turn(self, user_msg: str, assistant_msg: str) -> None:
        turn = {
            "user": user_msg,
            "assistant": assistant_msg,
            "timestamp": time.time(),
        }
        _session_memory[self.session_id].append(turn)
        if len(_session_memory[self.session_id]) > self.window_size * 2:
            self._persist_to_disk()
            _session_memory[self.session_id] = _session_memory[self.session_id][-self.window_size:]

    def get_short_term(self) -> List[Dict]:
        return self.turns[-self.window_size:]

    def get_context_string(self) -> str:
        recent = self.get_short_term()
        if not recent:
            return ""
        lines = []
        for turn in recent:
            lines.append(f"User: {turn['user']}")
            assistant_text = turn['assistant']
            if len(assistant_text) > 300:
                assistant_text = assistant_text[:300] + "..."
            lines.append(f"Assistant: {assistant_text}")
        return "\n".join(lines)

    def clear(self) -> None:
        _session_memory[self.session_id] = []
        logger.info(f"Memory cleared for session {self.session_id}")

    def _persist_to_disk(self) -> None:
        try:
            memory_dir = os.path.join(s.data_dir, "memory")
            os.makedirs(memory_dir, exist_ok=True)
            filepath = os.path.join(memory_dir, f"{self.session_id}.json")
            existing = []
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.extend(self.turns)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(existing[-100], f)
            logger.info(f"Persisted {len(self.turns)} turns to disk for session {self.session_id}")
        except Exception as e:
            logger.error(f"Memory persistence failed: {e}")

    def load_long_term(self) -> List[Dict]:
        try:
            filepath = os.path.join(s.data_dir, "memory", f"{self.session_id}.json")
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load long-term memory: {e}")
        return []


# ═══════════════════════════════════════════════════
# 5. LLM Service
# ═══════════════════════════════════════════════════

def _get_openai_client() -> Optional[OpenAI]:
    api_key = s.openai_api_key
    if not api_key:
        return None
    if s.openai_base_url:
        return OpenAI(api_key=api_key, base_url=s.openai_base_url)
    return OpenAI(api_key=api_key)


def _format_history(history: List[Dict[str, str]]) -> str:
    if not history:
        return ""
    lines = []
    for turn in history[-5:]:
        if isinstance(turn, dict):
            role = turn.get("role", "user")
            content = turn.get("content", "")
            lines.append(f"{role.capitalize()}: {content}")
    return "\n".join(lines) if lines else ""


def rewrite_query(query: str, history: List[Dict[str, str]] = None) -> str:
    if not history or len(history) < 2:
        return query
    cache_key = f"rewrite:{query}:{len(history)}"
    cached = llm_cache.get(cache_key)
    if cached is not None:
        return cached
    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; returning original query")
        return query
    history_str = _format_history(history)
    prompt = QUERY_REWRITE_PROMPT.format(history=history_str, query=query)
    try:
        response = client.chat.completions.create(
            model=s.openai_chat_model,
            messages=[
                {"role": "system", "content": "You are a query rewriting assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=100,
        )
        rewritten = response.choices[0].message.content.strip()
        llm_cache.set(cache_key, rewritten)
        return rewritten
    except Exception as exc:
        logger.error(f"Query rewrite failed: {exc}", exc_info=True)
        return query


def generate_answer(
    query: str,
    context: str = "",
    history: List[Dict[str, str]] = None,
    no_context: bool = False,
) -> str:
    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; cannot generate answer")
        raise OpenAIAPIError("OpenAI API key not configured.")

    history_str = _format_history(history) if history else ""
    if no_context:
        prompt = f"{SYSTEM_PROMPT}\n\n## Conversation History\n{history_str}\n\n## Question\n{query}\n\nProvide a helpful response."
    else:
        prompt = RAG_PROMPT_TEMPLATE.format(
            system_prompt=SYSTEM_PROMPT,
            context=context,
            history=history_str,
            query=query
        )

    try:
        response = client.chat.completions.create(
            model=s.openai_chat_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=s.llm_temperature,
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()
    except RateLimitError as exc:
        if "insufficient_quota" in str(exc).lower():
            logger.error(f"OpenAI quota exceeded: {exc}")
            raise OpenAIQuotaExceededException()
        else:
            logger.error(f"OpenAI rate limit: {exc}")
            raise OpenAIAPIError("OpenAI API rate limit exceeded. Please try again in a moment.")
    except APIError as exc:
        logger.error(f"OpenAI API error: {exc}")
        raise OpenAIAPIError(f"OpenAI API error: {str(exc)[:100]}")
    except Exception as exc:
        logger.error(f"Answer generation failed: {exc}", exc_info=True)
        raise OpenAIAPIError()


async def stream_answer(
    query: str,
    context: str = "",
    history: List[Dict[str, str]] = None,
    no_context: bool = False,
):
    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; cannot stream answer")
        yield "I'm unable to generate a response at this time. Please add OPENAI_API_KEY."
        return

    history_str = _format_history(history) if history else ""
    if no_context:
        prompt = f"{SYSTEM_PROMPT}\n\n## Conversation History\n{history_str}\n\n## Question\n{query}\n\nProvide a helpful response."
    else:
        prompt = RAG_PROMPT_TEMPLATE.format(
            system_prompt=SYSTEM_PROMPT,
            context=context,
            history=history_str,
            query=query
        )

    try:
        with client.chat.completions.create(
            model=s.openai_chat_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=s.llm_temperature,
            max_tokens=1000,
            stream=True,
        ) as stream:
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
    except Exception as exc:
        logger.error(f"Stream answer failed: {exc}", exc_info=True)
        yield f"Error during streaming: {str(exc)}"


# ═══════════════════════════════════════════════════
# 6. Suggestions
# ═══════════════════════════════════════════════════

def generate_actions(query: str, answer: str) -> Tuple[List[Dict[str, str]], float]:
    prompt = ACTION_SUGGESTION_PROMPT.format(query=query, answer=answer[:500])
    messages = [
        {"role": "system", "content": "Generate a small set of follow-up actions based on the query and answer."},
        {"role": "user", "content": prompt},
    ]

    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; skipping action generation.")
        return [], 0.0

    try:
        response = client.chat.completions.create(
            model=s.openai_chat_model,
            messages=messages,
            temperature=0.1,
            max_tokens=256,
        )
        content = response.choices[0].message.content.strip()
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Invalid JSON from action engine: {content[:100] if 'content' in dir() else 'unknown'}")
        return [], 0.0
    except (RateLimitError, APIError) as exc:
        logger.warning(f"Action suggestion skipped (quota/API): {exc}")
        return [], 0.0
    except Exception as exc:
        logger.error(f"Action generation failed: {exc}", exc_info=True)
        return [], 0.0

    raw_actions = parsed.get("actions", []) if isinstance(parsed, dict) else []
    confidence = float(parsed.get("confidence_score", 0.0)) if isinstance(parsed, dict) else 0.0

    clean_actions = []
    for a in raw_actions:
        if not isinstance(a, dict):
            continue
        clean_actions.append({
            "label": str(a.get("label", "Follow up"))[:80],
            "type": str(a.get("type", "query")),
            "payload": str(a.get("payload", a.get("label", ""))),
        })

    return clean_actions[:3], min(confidence, 100.0)


# ═══════════════════════════════════════════════════
# 7. Chunking
# ═══════════════════════════════════════════════════

def chunk_text(text: str, document_id: str) -> List[Dict[str, Any]]:
    paragraphs = re.split(r'\n{2,}', text)
    chunks: List[Dict[str, Any]] = []
    current_paragraphs: List[str] = []
    current_length = 0
    current_page = 1

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
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

    if current_paragraphs:
        chunks.append({
            "document_id": document_id,
            "page": current_page,
            "text": " ".join(current_paragraphs),
        })

    logger.info(f"Chunked document {document_id}: {len(chunks)} chunks created")
    return chunks


# ═══════════════════════════════════════════════════
# 8. Ingestion
# ═══════════════════════════════════════════════════

def ingest_pdf(file_bytes: bytes, filename: str) -> tuple[str, int]:
    from app.services.embeddings import get_document_embeddings

    doc_id = str(uuid.uuid4())[:8] + "_" + filename.replace(" ", "_").lower().replace(".pdf", "")

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

    chunks = chunk_text(raw_text, doc_id)
    if not chunks:
        raise ValueError("Chunking produced zero chunks")

    texts_to_embed = [c["text"] for c in chunks]
    embeddings = get_document_embeddings(texts_to_embed)

    for i, chunk in enumerate(chunks):
        chunk["embedding"] = embeddings[i]

    os.makedirs(s.data_dir, exist_ok=True)
    store_path = os.path.join(s.data_dir, f"{doc_id}.json")
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f)

    logger.info(f"Ingested '{filename}' -> {doc_id} ({len(chunks)} chunks)")
    return doc_id, len(chunks)


def load_all_chunks(allowed_docs: List[str] = None) -> List[dict]:
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
    if not os.path.exists(s.data_dir):
        return 0
    return len([f for f in os.listdir(s.data_dir) if f.endswith(".json")])


# ═══════════════════════════════════════════════════
# 9. Retriever
# ═══════════════════════════════════════════════════

def _tokenize(text: str) -> List[str]:
    return re.findall(r'\w+', text.lower())


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    a, b = np.array(v1, dtype=np.float32), np.array(v2, dtype=np.float32)
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def hybrid_search(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = None,
) -> List[Dict[str, Any]]:
    from app.services.embeddings import get_query_embedding

    if not chunks:
        return []

    top_k = top_k or s.top_k_retrieval

    corpus_tokens = [_tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(corpus_tokens)
    query_tokens = _tokenize(query)
    bm25_scores = bm25.get_scores(query_tokens)

    query_embedding = get_query_embedding(query)
    vector_scores = np.array([
        cosine_similarity(query_embedding, c.get("embedding", [0.0] * len(query_embedding)))
        for c in chunks
    ], dtype=np.float32)

    def normalize(scores: np.ndarray) -> np.ndarray:
        min_s, max_s = scores.min(), scores.max()
        if max_s - min_s == 0:
            return np.zeros_like(scores)
        return (scores - min_s) / (max_s - min_s)

    bm25_norm = normalize(np.array(bm25_scores, dtype=np.float32))
    vector_norm = normalize(vector_scores)

    fusion_scores = (s.bm25_weight * bm25_norm) + (s.vector_weight * vector_norm)

    scored_chunks = []
    for i, chunk in enumerate(chunks):
        scored_chunks.append({
            **chunk,
            "score": float(fusion_scores[i]),
            "bm25_score": float(bm25_norm[i]),
            "vector_score": float(vector_norm[i]),
        })

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    top_results = scored_chunks[:top_k]

    if top_results:
        logger.info(f"Hybrid search: {len(chunks)} chunks -> top-{top_k} (best score: {top_results[0]['score']:.3f})")
    else:
        logger.info("Hybrid search: no results")

    return top_results


# ═══════════════════════════════════════════════════
# 10. Reranker
# ═══════════════════════════════════════════════════

RERANK_PROMPT = """Rate the relevance of the following document excerpt to the query on a scale of 0 to 10.
Output ONLY a JSON object: {{"score": <number>}}

Query: {query}

Document Excerpt:
{text}

Relevance JSON:"""


def rerank_chunks(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = None,
) -> List[Dict[str, Any]]:
    if not s.rerank_enabled or not chunks:
        return chunks

    top_k = top_k or s.top_k_retrieval
    reranked = []

    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; skipping rerank.")
        for chunk in chunks[:top_k]:
            chunk["rerank_score"] = chunk.get("score", 0)
            reranked.append(chunk)
        reranked.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        final = reranked[:top_k]
        logger.info(f"Reranked {len(chunks)} -> {len(final)} chunks")
        return final

    for chunk in chunks[:top_k + 2]:
        prompt = RERANK_PROMPT.format(query=query, text=chunk["text"][:500])
        messages = [
            {"role": "system", "content": "Score the relevance of a document excerpt to the query."},
            {"role": "user", "content": prompt},
        ]
        try:
            response = client.chat.completions.create(
                model=s.openai_chat_model,
                messages=messages,
                temperature=0.0,
                max_tokens=32,
            )
            content = response.choices[0].message.content.strip()
            parsed = json.loads(content)
            relevance = float(parsed.get("score", 0))
            chunk["rerank_score"] = relevance / 10.0
        except Exception as exc:
            logger.warning(f"Rerank failed for chunk: {exc}")
            chunk["rerank_score"] = chunk.get("score", 0)
        reranked.append(chunk)

    reranked.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    final = reranked[:top_k]
    logger.info(f"Reranked {len(chunks)} -> {len(final)} chunks")
    return final


# ═══════════════════════════════════════════════════
# 11. Pipeline Orchestrator
# ═══════════════════════════════════════════════════

def run_pipeline(
    query: str,
    document_ids: List[str] = None,
    history: List[Dict[str, str]] = None,
    session_id: str = "default",
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    pipeline_start = time.time()
    memory = MemoryManager(session_id)

    cache_key = f"{query}:{','.join(document_ids or [])}"
    cached = query_cache.get(cache_key)
    if cached:
        logger.info("Cache hit for query")
        return cached

    rewrite_start = time.time()
    if history and len(history) > 1:
        rewritten_query = rewrite_query(query, history)
        logger.info(f"Query rewritten: '{query}' -> '{rewritten_query}' ({time.time() - rewrite_start:.2f}s)")
    else:
        rewritten_query = query

    chunks = load_all_chunks(document_ids if document_ids else None)

    if not chunks:
        try:
            answer = generate_answer(query, "", history, no_context=True)
        except (OpenAIQuotaExceededException, OpenAIAPIError):
            raise
        actions, conf = generate_actions(query, answer)
        result = (answer, [], {
            "confidence_score": conf,
            "suggested_actions": actions,
            "latency_ms": round((time.time() - pipeline_start) * 1000, 1),
        })
        return result

    retrieval_start = time.time()
    retrieved = hybrid_search(rewritten_query, chunks, top_k=s.top_k_retrieval + 3)
    logger.info(f"Retrieval: {len(retrieved)} chunks in {time.time() - retrieval_start:.2f}s")

    rerank_start = time.time()
    if s.rerank_enabled and len(retrieved) > 2:
        top_chunks = rerank_chunks(rewritten_query, retrieved, top_k=s.top_k_retrieval)
    else:
        top_chunks = retrieved[:s.top_k_retrieval]
    logger.info(f"Reranking: {len(top_chunks)} final chunks in {time.time() - rerank_start:.2f}s")

    context_text = "\n\n---\n\n".join([
        f"[Source: {c['document_id']} | Page {c['page']}]\n{c['text']}"
        for c in top_chunks
    ])

    memory_context = memory.get_context_string()
    if memory_context:
        context_text = f"## Previous Conversation Context\n{memory_context}\n\n## Document Context\n{context_text}"

    gen_start = time.time()
    try:
        answer = generate_answer(query, context_text, history)
    except (OpenAIQuotaExceededException, OpenAIAPIError):
        raise
    logger.info(f"Answer generation: {time.time() - gen_start:.2f}s")

    action_start = time.time()
    actions, confidence = generate_actions(query, answer)
    logger.info(f"Action generation: {time.time() - action_start:.2f}s")

    citations = []
    for c in top_chunks:
        score = c.get("rerank_score", c.get("score", 0))
        if score > s.min_relevance_score:
            citations.append({
                "document_id": c["document_id"],
                "page": c["page"],
                "snippet": c["text"][:200] + "...",
                "relevance_score": round(score, 3),
            })

    memory.add_turn(query, answer)

    total_latency = round((time.time() - pipeline_start) * 1000, 1)
    logger.info(f"Pipeline complete: {total_latency}ms total latency")

    extras = {
        "confidence_score": confidence,
        "suggested_actions": actions,
        "latency_ms": total_latency,
        "eval_metrics": {
            "retrieved_chunks": len(top_chunks),
            "citation_count": len(citations),
            "rerank_enabled": s.rerank_enabled,
        },
    }

    result = (answer, citations, extras)
    query_cache.set(cache_key, result)
    return result


async def stream_pipeline(
    query: str,
    document_ids: List[str] = None,
    history: List[Dict[str, str]] = None,
    session_id: str = "default",
):
    pipeline_start = time.time()
    memory = MemoryManager(session_id)

    if history and len(history) > 1:
        rewritten_query = rewrite_query(query, history)
    else:
        rewritten_query = query

    chunks = load_all_chunks(document_ids if document_ids else None)

    if not chunks:
        context_text = ""
        no_context = True
    else:
        retrieved = hybrid_search(rewritten_query, chunks, top_k=s.top_k_retrieval + 3)
        if s.rerank_enabled and len(retrieved) > 2:
            top_chunks = rerank_chunks(rewritten_query, retrieved, top_k=s.top_k_retrieval)
        else:
            top_chunks = retrieved[:s.top_k_retrieval]

        context_text = "\n\n---\n\n".join([
            f"[Source: {c['document_id']} | Page {c['page']}]\n{c['text']}"
            for c in top_chunks
        ])
        memory_context = memory.get_context_string()
        if memory_context:
            context_text = f"## Previous Conversation Context\n{memory_context}\n\n## Document Context\n{context_text}"
        no_context = False

    full_answer = ""
    async for token in stream_answer(query, context_text, history, no_context=no_context):
        full_answer += token
        yield {"type": "token", "content": token}

    actions, confidence = generate_actions(query, full_answer)

    citations = []
    if chunks and not no_context:
        for c in top_chunks:
            score = c.get("rerank_score", c.get("score", 0))
            if score > s.min_relevance_score:
                citations.append({
                    "document_id": c["document_id"],
                    "page": c["page"],
                    "snippet": c["text"][:200] + "...",
                    "relevance_score": round(score, 3),
                })

    memory.add_turn(query, full_answer)
    total_latency = round((time.time() - pipeline_start) * 1000, 1)

    yield {
        "type": "metadata",
        "data": {
            "citations": citations,
            "confidence_score": confidence,
            "suggested_actions": actions,
            "latency_ms": total_latency,
        }
    }

    yield {"type": "done"}
