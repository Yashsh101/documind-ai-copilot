from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 800
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k_retrieval: int = 5
    min_relevance_score: float = 0.30
    max_history_turns: int = 6
    vector_store_dir: str = "vector_store"
    uploads_dir: str = "uploads"
    api_title: str = "DocuMind — AI Customer Support Copilot"
    api_version: str = "1.0.0"
    allowed_origins: list[str] = ["*"]

@lru_cache
def get_settings() -> Settings:
    return Settings()