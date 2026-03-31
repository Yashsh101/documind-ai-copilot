from datetime import datetime
import httpx
from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["health"])
settings = get_settings()


@router.get("/health")
async def health_check():
    ollama_status = "offline"

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            if response.status_code == 200:
                ollama_status = "online"
    except Exception:
        ollama_status = "offline"

    return {
        "status": "ok",
        "service": "DocuMind API",
        "timestamp": datetime.utcnow().isoformat(),
        "llm": {
            "provider": "ollama",
            "model": settings.llm_model,
            "status": ollama_status,
        },
    }