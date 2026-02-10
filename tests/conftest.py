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
from app.db import init_db
from app.main import app

FIXTURES_DIR = Path(__file__).parent / "fixtures"

DATABASE_URL = "postgresql+asyncpg://dev:dev@localhost:5432/estimations"
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
ALEMBIC_BIN = str(Path(sys.executable).parent / "alembic")


def get_test_settings() -> Settings:
    return Settings(
        DATABASE_URL=DATABASE_URL,
        ENVIRONMENT="development",
        LOG_LEVEL="DEBUG",
        API_KEY="test-api-key",
        OPENAI_API_KEY="test-key",
    )


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> None:
    env = {**os.environ, "DATABASE_URL": DATABASE_URL}
    subprocess.run(
        [ALEMBIC_BIN, "upgrade", "head"],
        check=True,
        env=env,
        cwd=PROJECT_ROOT,
    )
    yield  # type: ignore[misc]
    subprocess.run(
        [ALEMBIC_BIN, "downgrade", "base"],
        check=True,
        env=env,
        cwd=PROJECT_ROOT,
    )


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
        return [[0.1] * 1536 for _ in texts]

    service.generate_embeddings = AsyncMock(side_effect=mock_generate)
    service._model = "test-embedding-model"
    return service


@pytest.fixture
async def client_with_mock_embeddings() -> AsyncIterator[AsyncClient]:
    from sqlalchemy import text as sa_text

    from app.dependencies import get_embedding_service

    test_settings = get_test_settings()
    init_db(test_settings)

    mock_emb_service = _make_mock_embedding_service()

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_embedding_service] = lambda: mock_emb_service

    # Clean tables before each test to ensure isolation
    engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(sa_text("DELETE FROM rag.ingestion_logs"))
        await conn.execute(sa_text("DELETE FROM rag.chunks"))
        await conn.execute(sa_text("DELETE FROM rag.documents"))
    await engine.dispose()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- pytest CLI options ---


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live-api",
        action="store_true",
        default=False,
        help="Run tests that call live external APIs (OpenAI)",
    )


@pytest.fixture
def live_api(request: pytest.FixtureRequest) -> bool:
    return request.config.getoption("--live-api")  # type: ignore[return-value]
