"""Tests TDD para RAG-01: verifican la configuración esperada post-migración a Gemini.

Estos tests FALLAN con el código actual (config.py tiene settings de OpenAI).
Eso es intencional — es TDD Wave 1.
"""

import pytest

from app.config import Settings


def test_gemini_api_key_setting_exists() -> None:
    """Settings debe tener GEMINI_API_KEY, no OPENAI_API_KEY."""
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://dev:dev@localhost:5432/test",
        GEMINI_API_KEY="test-key",
    )
    assert s.GEMINI_API_KEY == "test-key"


def test_embedding_dimensions_is_768() -> None:
    """EMBEDDING_DIMENSIONS debe ser 768 por defecto."""
    s = Settings(DATABASE_URL="postgresql+asyncpg://dev:dev@localhost:5432/test")
    assert s.EMBEDDING_DIMENSIONS == 768


def test_embedding_model_is_multilingual() -> None:
    """EMBEDDING_MODEL debe ser text-multilingual-embedding-002."""
    s = Settings(DATABASE_URL="postgresql+asyncpg://dev:dev@localhost:5432/test")
    assert s.EMBEDDING_MODEL == "text-multilingual-embedding-002"


def test_llm_model_is_gemini_flash() -> None:
    """LLM_MODEL debe ser gemini-2.5-flash."""
    s = Settings(DATABASE_URL="postgresql+asyncpg://dev:dev@localhost:5432/test")
    assert s.LLM_MODEL == "gemini-2.5-flash"


def test_no_openai_api_key() -> None:
    """Settings NO debe tener atributo OPENAI_API_KEY."""
    s = Settings(DATABASE_URL="postgresql+asyncpg://dev:dev@localhost:5432/test")
    assert not hasattr(s, "OPENAI_API_KEY"), (
        "Settings still exposes OPENAI_API_KEY — remove it in RAG-01"
    )


def test_database_schema_is_her() -> None:
    """DATABASE_SCHEMA debe ser 'her' por defecto."""
    s = Settings(DATABASE_URL="postgresql+asyncpg://dev:dev@localhost:5432/test")
    assert s.DATABASE_SCHEMA == "her"
