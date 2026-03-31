from datetime import datetime
from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["health"])
settings = get_settings()


@router.get("/health")
async def health_check():
    openai_status = "online" if settings.openai_api_key else "offline"

    return {
        "status": "ok",
        "service": "DocuMind API",
        "timestamp": datetime.utcnow().isoformat(),
        "provider": "openai",
        "llm": {
            "model": settings.openai_chat_model,
            "status": openai_status,
        },
    }