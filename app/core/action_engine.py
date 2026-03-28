import json
from openai import AsyncOpenAI
from app.config import get_settings
from app.utils.logger import logger

_ACTION_PROMPT = """\
You are an AI customer support decision engine.
Based on the user's query and the provided answer, determine the user's intent 
and suggest 1 to 3 logical next actions they can take (e.g., "Request a refund", "Contact support", "Track order").

Output ONLY a JSON array of strings representing the actions. Do not wrap it in markdown block.
Example: ["Request refund", "Track refund status"]

User Query: {query}
Generated Answer: {answer}

Actions (JSON array only):"""

async def suggest_actions(query: str, answer: str) -> list[str]:
    """
    Suggests next actions based on user query and generated answer
    using a separate lightweight LLM call (e.g., gpt-4o-mini).
    """
    if not answer or "I don't have enough information" in answer:
        return ["Contact Support"]
        
    s = get_settings()
    client = AsyncOpenAI(api_key=s.openai_api_key)
    try:
        r = await client.chat.completions.create(
            model=s.llm_model, # gpt-4o-mini is suitable for this simple task
            messages=[{"role":"user","content":_ACTION_PROMPT.format(query=query, answer=answer)}],
            temperature=0.0, 
            max_tokens=50
        )
        content = (r.choices[0].message.content or "").strip()
        # Clean up possible markdown artifacts if any
        if content.startswith("```json"):
            content = content.replace("```json", "", 1)
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        actions = json.loads(content)
        if isinstance(actions, list):
            logger.info(f"Action engine suggested: {actions}")
            return actions[:3]
    except Exception as e:
        logger.warning(f"Action engine failed gracefully: {e}")
        
    return ["Contact Support"]
