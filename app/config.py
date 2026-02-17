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
    DATABASE_SCHEMA: str = "rag"
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

    # OpenAI
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    LLM_MODEL: str = "gpt-4o"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.2
    LLM_TIMEOUT: int = 30

    # Search defaults
    DEFAULT_TOP_K: int = 10
    DEFAULT_MIN_SIMILARITY: float = 0.6
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
    def embedding_dimensions_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("EMBEDDING_DIMENSIONS must be a positive integer")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
