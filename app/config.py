"""
DocuMind v3 — Centralized Configuration & Structured Logging
"""
import os
import json
import logging
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from dotenv import load_dotenv

load_dotenv(override=True)


class _JSONFormatter(logging.Formatter):
    """Production-grade structured JSON log formatter."""
    def format(self, record):
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _make_logger(name: str, level: str = "INFO") -> logging.Logger:
    log = logging.getLogger(name)
    if log.handlers:
        return log
    handler = logging.StreamHandler()
    handler.setFormatter(_JSONFormatter())
    log.addHandler(handler)
    log.setLevel(getattr(logging, level.upper(), logging.INFO))
    log.propagate = False
    return log


logger = _make_logger("documind", os.getenv("LOG_LEVEL", "INFO"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    api_title: str = "DocuMind v3 — AI Customer Support Copilot"
    api_version: str = "3.0.0"
    data_dir: str = "data"
    log_level: str = "INFO"

    # RAG Pipeline
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k_retrieval: int = 5
    min_relevance_score: float = 0.25
    embedding_cache_size: int = 2000

    # Hybrid Search Weights
    bm25_weight: float = 0.35
    vector_weight: float = 0.65
    rerank_enabled: bool = True

    # Ollama / LLM
    ollama_base_url: str = Field(default="http://localhost:11434")
    llm_model: str = "llama3"
    llm_temperature: float = 0.15

    # Memory
    memory_window_size: int = 10


@lru_cache()
def get_settings() -> Settings:
    return Settings()