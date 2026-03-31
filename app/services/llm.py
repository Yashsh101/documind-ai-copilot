import os
from typing import Dict, List, Optional

from openai import OpenAI
from app.config import get_settings, logger

s = get_settings()
SYSTEM_PROMPT = "You are an expert AI support assistant."


def _get_openai_client() -> Optional[OpenAI]:
    api_key = s.openai_api_key
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

def _build_messages(
    query: str,
    context: str = "",
    history: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append(
            {
                "role": "system",
                "content": f"Use the following context when answering the user's question:\n\n{context}",
            }
        )

    if history:
        for turn in history[-10:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": query})
    return messages


def generate_answer(
    query: str,
    context: str = "",
    history: Optional[List[Dict[str, str]]] = None,
    no_context: bool = False,
) -> str:
    messages = _build_messages(query, "" if no_context else context, history)
    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; returning placeholder answer.")
        return "OpenAI API key is not configured. Please set OPENAI_API_KEY to generate an answer."

    try:
        response = client.chat.completions.create(
            model=s.openai_chat_model,
            messages=messages,
            temperature=s.llm_temperature,
            max_tokens=1024,
        )
        return response.choices[0].message["content"].strip()
    except Exception as exc:
        logger.error(f"OpenAI generate_answer failed: {exc}", exc_info=True)
        return "I'm sorry, I could not generate an answer at this time."


def rewrite_query(query: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    if not history:
        return query

    conversation = "\n".join(
        [f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in history[-6:]]
    )
    prompt = (
        "Rewrite the user's latest question so it is clear and self-contained."
        f"\n\nConversation history:\n{conversation}\n\nQuestion: {query}\n\nStandalone question:"
    )

    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; skipping rewrite_query.")
        return query

    try:
        response = client.chat.completions.create(
            model=s.openai_chat_model,
            messages=[
                {"role": "system", "content": "Rewrite user questions into standalone queries."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=128,
        )
        rewritten = response.choices[0].message["content"].strip()
        return rewritten or query
    except Exception as exc:
        logger.warning(f"OpenAI rewrite_query fallback: {exc}", exc_info=True)
        return query


async def stream_answer(
    query: str,
    context: str = "",
    history: Optional[List[Dict[str, str]]] = None,
    no_context: bool = False,
):
    messages = _build_messages(query, "" if no_context else context, history)
    client = _get_openai_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; streaming placeholder answer.")
        yield "OpenAI API key is not configured. Please set OPENAI_API_KEY to stream an answer."
        return

    try:
        async with client.chat.completions.stream(
            model=s.openai_chat_model,
            messages=messages,
            temperature=s.llm_temperature,
            max_tokens=1024,
        ) as stream:
            async for event in stream:
                token = None
                event_type = getattr(event, "type", None)
                if event_type in {"response.output_text.delta", "response.delta", "message.delta", "delta"}:
                    token_value = getattr(event, "delta", None)
                    if isinstance(token_value, dict):
                        token = token_value.get("content") or token_value.get("text")
                    elif isinstance(token_value, str):
                        token = token_value
                elif event_type in {"response.completed", "message.complete"}:
                    break

                if token:
                    yield str(token)
    except Exception as exc:
        logger.error(f"OpenAI stream_answer failed: {exc}", exc_info=True)
        yield ""
