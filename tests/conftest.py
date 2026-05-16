import json
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import Settings, get_settings

FIXTURES_DIR = Path(__file__).parent / "fixtures"

DATABASE_URL = "postgresql+asyncpg://dev:dev@localhost:5433/her_poc"
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
ALEMBIC_BIN = str(Path(sys.executable).parent / "alembic")


def get_test_settings() -> Settings:
    return Settings(
        DATABASE_URL=DATABASE_URL,
        ENVIRONMENT="development",
        LOG_LEVEL="DEBUG",
        API_KEY="test-api-key",
        GEMINI_API_KEY="test-gemini-key",
    )


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> None:
    env = {**os.environ, "DATABASE_URL": DATABASE_URL}
    try:
        subprocess.run(
            [ALEMBIC_BIN, "upgrade", "head"],
            check=True,
            env=env,
            cwd=PROJECT_ROOT,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass  # DB not available; tests that need it will fail individually.
    yield  # type: ignore[misc]
    try:
        subprocess.run(
            [ALEMBIC_BIN, "downgrade", "base"],
            check=True,
            env=env,
            cwd=PROJECT_ROOT,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        await trans.rollback()
    await engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return get_test_settings()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from app.db import init_db
    from app.main import app

    test_settings = get_test_settings()
    init_db(test_settings)

    app.dependency_overrides[get_settings] = get_test_settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- Fixture helpers for JSON test data ---


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())  # type: ignore[no-any-return]


@pytest.fixture
def full_quote_json() -> dict[str, Any]:
    return _load_fixture("quote_platform_ia.json")


@pytest.fixture
def minimal_quote_json() -> dict[str, Any]:
    return _load_fixture("quote_minimal.json")


# --- Mock embedding service for integration tests ---


def _make_mock_embedding_service() -> MagicMock:
    service = MagicMock()

    async def mock_generate(texts: list[str]) -> list[list[float]]:
        return [[0.1] * 768 for _ in texts]

    service.generate_embeddings = AsyncMock(side_effect=mock_generate)
    service.generate_single_embedding = AsyncMock(
        side_effect=lambda text, task_type="RETRIEVAL_DOCUMENT": [0.1] * 768
    )
    service._model = "text-multilingual-embedding-002"
    return service


@pytest.fixture
async def client_with_mock_embeddings() -> AsyncIterator[AsyncClient]:
    from app.db import init_db
    from app.dependencies import get_embedding_service
    from app.main import app

    test_settings = get_test_settings()
    init_db(test_settings)

    mock_emb_service = _make_mock_embedding_service()

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_embedding_service] = lambda: mock_emb_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- Mock generation service for LLM integration tests ---


def _make_mock_generation_service() -> MagicMock:
    service = MagicMock()
    service.generate = AsyncMock(
        return_value="Respuesta de prueba del modelo Gemini."
    )
    return service


@pytest.fixture
async def client_with_mock_llm() -> AsyncIterator[AsyncClient]:
    from app.db import init_db
    from app.dependencies import get_embedding_service, get_generation_service
    from app.main import app

    test_settings = get_test_settings()
    init_db(test_settings)

    mock_emb_service = _make_mock_embedding_service()
    mock_gen_service = _make_mock_generation_service()

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_embedding_service] = lambda: mock_emb_service
    app.dependency_overrides[get_generation_service] = lambda: mock_gen_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


