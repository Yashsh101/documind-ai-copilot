"""
DocuMind v3 — LLM Service (Ollama)

Handles all LLM interactions: answer generation, query rewriting, and streaming.
Supports dual-model fallback for reliability.
"""
import httpx
from typing import List, Dict, Optional, Generator
from app.config import get_settings, logger
from app.core.prompts import (
    SYSTEM_PROMPT,
    RAG_PROMPT_TEMPLATE,
    QUERY_REWRITE_PROMPT,
    NO_CONTEXT_PROMPT,
)
from app.core.cache import llm_cache

s = get_settings()

_FALLBACK_MODELS = [s.llm_model, "phi3", "mistral"]


def _build_prompt(
    query: str,
    context: str,
    history: List[Dict[str, str]] = None,
    no_context: bool = False,
) -> str:
    """Construct the full LLM prompt from template + context + history."""
    if no_context:
        return NO_CONTEXT_PROMPT.format(
            system_prompt=SYSTEM_PROMPT,
            query=query,
        )

    hist_str = ""
    if history:
        recent = history[-(s.memory_window_size):]
        hist_str = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in recent
        ])

    return RAG_PROMPT_TEMPLATE.format(
        system_prompt=SYSTEM_PROMPT,
        context=context,
        history=hist_str or "(No previous conversation)",
        query=query,
    )


def generate_answer(
    query: str,
    context: str,
    history: List[Dict[str, str]] = None,
    no_context: bool = False,
) -> str:
    """
    Generate a complete answer using Ollama LLM.
    Tries primary model, falls back to alternatives on failure.
    """
    # Check cache
    cache_key = f"ans:{query}:{context[:200]}"
    cached = llm_cache.get(cache_key)
    if cached:
        return cached

    full_prompt = _build_prompt(query, context, history, no_context)

    for attempt in range(2):
        for model in _FALLBACK_MODELS:
            payload = {
                "model": model,
                "prompt": full_prompt,
                "stream": False,
                "options": {"temperature": s.llm_temperature},
            }
            try:
                with httpx.Client(timeout=120) as client:
                    resp = client.post(f"{s.ollama_base_url}/api/generate", json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    content = data.get("response", "")
                    if content:
                        llm_cache.set(cache_key, content)
                        return content
            except httpx.TimeoutException:
                logger.warning(f"LLM timeout: model={model}, attempt={attempt + 1}")
            except httpx.RequestError as e:
                logger.error(f"LLM connection error: {e}")
            except Exception as e:
                logger.error(f"LLM generation failed: model={model}, error={e}")

    return (
        "I'm unable to connect to the intelligence engine right now. "
        "Please ensure Ollama is running (`ollama serve`) with the required model loaded."
    )


def stream_answer(
    query: str,
    context: str,
    history: List[Dict[str, str]] = None,
    no_context: bool = False,
) -> Generator[str, None, None]:
    """
    Stream answer tokens from Ollama. Yields individual tokens as they arrive.
    """
    full_prompt = _build_prompt(query, context, history, no_context)

    payload = {
        "model": s.llm_model,
        "prompt": full_prompt,
        "stream": True,
        "options": {"temperature": s.llm_temperature},
    }

    try:
        with httpx.Client(timeout=180) as client:
            with client.stream(
                "POST",
                f"{s.ollama_base_url}/api/generate",
                json=payload,
                timeout=180,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        import json
                        try:
                            data = json.loads(line)
                            token = data.get("response", "")
                            if token:
                                yield token
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        logger.error(f"Stream generation failed: {e}")
        yield f"\n\n⚠️ Streaming interrupted: {str(e)}"


def rewrite_query(query: str, history: List[Dict[str, str]]) -> str:
    """
    Rewrite a query to be self-contained using conversation history.
    Lightweight call — fast model, low token count.
    """
    hist_str = "\n".join([
        f"{m['role'].upper()}: {m['content']}"
        for m in history[-(s.memory_window_size):]
    ])

    prompt = QUERY_REWRITE_PROMPT.format(history=hist_str, query=query)

    payload = {
        "model": s.llm_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 80},
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{s.ollama_base_url}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            rewritten = data.get("response", "").strip()
            return rewritten if rewritten else query
    except Exception as e:
        logger.warning(f"Query rewrite failed, using original: {e}")
        return query
