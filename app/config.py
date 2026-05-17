from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://dev:dev@localhost:5432/estimations"
    DATABASE_SCHEMA: str = "her"
    DATABASE_ECHO: bool = False

    # Service
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8000
    WORKERS: int = 1
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"
    API_VERSION: str = "v1"

    # API Keys
    API_KEY: str = "dev-api-key"

    # Gemini
    GEMINI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSIONS: int = 768
    LLM_MODEL: str = "gemini-2.5-flash"
    LLM_MAX_OUTPUT_TOKENS: int = 8192

    # Google Cloud (Speech / TTS)
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    STT_MODEL: str = "long"
    STT_LANGUAGE_CODE: str = "es-ES"
    TTS_LANGUAGE_CODE: str = "es-ES"
    TTS_VOICE_NAME: str = "es-ES-Neural2-A"

    # Search defaults
    DEFAULT_TOP_K: int = 10
    DEFAULT_MIN_SIMILARITY: float = 0.3
    MAX_TOP_K: int = 50
    HNSW_EF_SEARCH: int = 100

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_must_be_postgresql(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must start with 'postgresql'")
        return v

    @field_validator("EMBEDDING_DIMENSIONS")
    @classmethod
    def embedding_dimensions_must_be_valid(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("EMBEDDING_DIMENSIONS must be a positive integer")
        allowed = {768}
        if v not in allowed:
            raise ValueError(f"EMBEDDING_DIMENSIONS must be one of {allowed}, got {v}")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
