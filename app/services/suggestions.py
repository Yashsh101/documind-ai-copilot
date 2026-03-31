"""
DocuMind v3 — Smart Suggestions Engine

Generates contextual follow-up actions and a confidence score using OpenAI.
"""
import json
import os
from typing import List, Dict, Tuple, Optional
from openai import OpenAI
from app.config import get_settings, logger
from app.core.prompts import ACTION_SUGGESTION_PROMPT

s = get_settings()


def _get_openai_client() -> Optional[OpenAI]:
    api_key = s.openai_api_key
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def generate_actions(query: str, answer: str) -> Tuple[List[Dict[str, str]], float]:
    """
    Generate up to 3 contextual follow-up actions and a confidence score.

    Returns: (actions_list, confidence_score)
    """
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
        content = response.choices[0].message["content"].strip()
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Invalid JSON from action engine: {content[:100]}")
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
