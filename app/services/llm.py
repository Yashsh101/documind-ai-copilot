"""
DocuMind v3 — LLM Service Layer

Provides interfaces for:
1. Answer generation (RAG-augmented)
2. Query rewriting (context-aware)
3. Token streaming (async generators)

All implementations use OpenAI APIs only (no Ollama).
"""
from typing import Optional, List, Dict, Any
from openai import OpenAI
from app.config import get_settings, logger
from app.core.prompts import SYSTEM_PROMPT, RAG_PROMPT_TEMPLATE, QUERY_REWRITE_PROMPT
from app.core.cache import llm_cache

s = get_settings()


def _get_openai_client() -> Optional[OpenAI]:
    """Get OpenAI client if API key is available."""
    api_key = s.openai_api_key
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _format_history(history: List[Dict[str, str]]) -> str:
    """Convert conversation history list to formatted string."""
    if not history:
        return ""
    
    lines = []
    for turn in history[-5:]:  # Keep last 5 turns
        if isinstance(turn, dict):
            role = turn.get("role", "user")
            content = turn.get("content", "")
            lines.append(f"{role.capitalize()}: {content}")
    
    return "\n".join(lines) if lines else ""


def rewrite_query(query: str, history: List[Dict[str, str]] = None) -> str:
    """
    Rewrite user query to be self-contained and context-aware.
    Uses conversation history to resolve pronouns and references.
    """
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
    prompt = QUERY_REWRITE_PROMPT.format(
        history=history_str,
        query=query
    )
    
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
    """
    Generate answer using OpenAI with RAG context and conversation history.
    
    Args:
        query: User question
        context: Retrieved document context
        history: Conversation history
        no_context: If True, answer without context (fallback mode)
    
    Returns:
        Generated answer string
    """
    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; cannot generate answer")
        return "I'm unable to generate a response at this time. Please add OPENAI_API_KEY to your configuration."
    
    history_str = _format_history(history) if history else ""
    
    if no_context:
        # Fallback: no documents available
        prompt = f"{SYSTEM_PROMPT}\n\n## Conversation History\n{history_str}\n\n## Question\n{query}\n\nProvide a helpful response."
    else:
        # RAG mode: use context
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
        answer = response.choices[0].message.content.strip()
        return answer
    except Exception as exc:
        logger.error(f"Answer generation failed: {exc}", exc_info=True)
        return "An error occurred while generating the response. Please try again."


async def stream_answer(
    query: str,
    context: str = "",
    history: List[Dict[str, str]] = None,
    no_context: bool = False,
):
    """
    Stream answer tokens in real-time using OpenAI streaming API.
    Yields individual tokens as they arrive.
    Uses synchronous OpenAI client in async context.
    
    Args:
        query: User question
        context: Retrieved document context
        history: Conversation history
        no_context: If True, answer without context (fallback mode)
    
    Yields:
        Token strings
    """
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