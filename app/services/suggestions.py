"""
DocuMind v3 — Smart Suggestions Engine

Generates contextual follow-up actions and questions based on
the current query and response. Uses a separate lightweight LLM call.
"""
import json
import httpx
from typing import List, Dict, Tuple
from app.config import get_settings, logger
from app.core.prompts import ACTION_SUGGESTION_PROMPT

s = get_settings()


def generate_actions(query: str, answer: str) -> Tuple[List[Dict[str, str]], float]:
    """
    Generate up to 3 contextual follow-up actions and a confidence score.
    
    Returns: (actions_list, confidence_score)
    """
    prompt = ACTION_SUGGESTION_PROMPT.format(query=query, answer=answer[:500])

    models_to_try = [s.llm_model, "phi3"]

    for attempt in range(2):
        for model in models_to_try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1, "num_predict": 300},
            }

            try:
                with httpx.Client(timeout=45.0) as client:
                    resp = client.post(f"{s.ollama_base_url}/api/generate", json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    content = data.get("response", "{}")

                    if not content:
                        continue

                    try:
                        parsed = json.loads(content)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from action engine: {content[:100]}")
                        continue

                    raw_actions = parsed.get("actions", [])
                    confidence = float(parsed.get("confidence_score", 0.0))

                    # Validate and clean actions
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

            except httpx.TimeoutException:
                logger.warning(f"Action gen timeout: model={model}, attempt={attempt + 1}")
            except Exception as e:
                logger.error(f"Action generation failed: model={model}, error={e}")

    # Fallback: return empty actions with zero confidence
    return [], 0.0
