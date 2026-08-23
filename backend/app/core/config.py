import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings dynamically loaded from .env environment file.
    No hardcoded production settings reside in code.
    """
    DATABASE_URL: str = "sqlite:///tender_intelligence.db"
    TEST_DATABASE_URL: str | None = None

    LLM_API_KEY: str = ""
    LLM_MODEL: str = "groq/openai/gpt-oss-120b"
    LLM_FALLBACK_MODEL: str = "groq/qwen/qwen3.6-27b"

    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "jina-embeddings-v5-omni-small"
    EMBEDDING_DIMENSION: int = 768

    TIMEZONE: str = "Asia/Kolkata"
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"

    INGESTION_ENABLED: bool = True
    DISCOVERY_ENABLED: bool = False
    DISCOVERY_INTERVAL_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
