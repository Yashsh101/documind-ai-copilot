from datetime import datetime
import os
from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["health"])
settings = get_settings()


@router.get("/health")
async def health_check():
    openai_status = "online" if os.getenv("OPENAI_API_KEY") else "offline"

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