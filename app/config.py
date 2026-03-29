import os
import json
import logging
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from dotenv import load_dotenv

load_dotenv(override=True)

class _JSONFormatter(logging.Formatter):
    def format(self, record):
        p = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
             "level": record.levelname, "message": record.getMessage()}
        if record.exc_info: p["exc"] = self.formatException(record.exc_info)
        return json.dumps(p, default=str)

def _make_logger(name):
    log = logging.getLogger(name)
    if log.handlers: return log
    h = logging.StreamHandler()
    h.setFormatter(_JSONFormatter())
    log.addHandler(h)
    log.setLevel(logging.INFO)
    log.propagate = False
    return log

logger = _make_logger("documind")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    api_title: str = "DocuMind v2 \u2014 AI Customer Support Copilot"
    api_version: str = "2.0.0"
    data_dir: str = "data"
    
    # RAG Settings
    chunk_size: int = 400
    chunk_overlap: int = 80
    top_k_retrieval: int = 3
    embedding_cache_size: int = 1000

@lru_cache()
def get_settings() -> Settings:
    return Settings()