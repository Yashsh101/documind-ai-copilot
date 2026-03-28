from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1000
    chunk_size: int = 400
    chunk_overlap: int = 80
    top_k_retrieval: int = 20
    top_k_rerank: int = 5
    min_relevance_score: float = 0.25
    max_history_turns: int = 8
    vector_store_dir: str = "vector_store"
    uploads_dir: str = "uploads"
    api_title: str = "DocuMind v2 — AI Customer Support Copilot"
    api_version: str = "2.0.0"
    allowed_origins: list[str] = ["*"]
    hyde_enabled: bool = True
    hybrid_search_enabled: bool = True
    reranking_enabled: bool = True

@lru_cache
def get_settings() -> Settings:
    return Settings()