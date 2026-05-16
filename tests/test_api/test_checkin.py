"""API tests for the check-in endpoints — requires DB, EmbeddingService mocked."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool, text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from tests.conftest import DATABASE_URL, get_test_settings


def _make_mock_embedding_service() -> MagicMock:
    service = MagicMock()
    service.generate_embeddings = AsyncMock(
        side_effect=lambda texts, task_type="RETRIEVAL_DOCUMENT": [[0.1] * 768 for _ in texts]
    )
    return service


@pytest.fixture
async def client_for_checkin() -> AsyncIterator[AsyncClient]:
    from app.db import init_db
    from app.dependencies import get_checkin_service, get_embedding_service
    from app.main import app
    from app.services.checkin_service import CheckInService

    test_settings = get_test_settings()
    init_db(test_settings)
    mock_emb = _make_mock_embedding_service()

    # Clean her.* tables before each test.
    engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(sa_text("DELETE FROM her.check_in_chunks"))
        await conn.execute(sa_text("DELETE FROM her.check_ins"))
        await conn.execute(sa_text("DELETE FROM her.employees"))
    await engine.dispose()

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_embedding_service] = lambda: mock_emb

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/checkin/start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_returns_session_id_and_question(
    client_for_checkin: AsyncClient,
) -> None:
    resp = await client_for_checkin.post("/api/v1/checkin/start")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["question_text"] == "¡Hola! Soy HER. ¿Cómo te llamas?"


@pytest.mark.asyncio
async def test_start_returns_unique_session_ids(
    client_for_checkin: AsyncClient,
) -> None:
    r1 = await client_for_checkin.post("/api/v1/checkin/start")
    r2 = await client_for_checkin.post("/api/v1/checkin/start")
    assert r1.json()["session_id"] != r2.json()["session_id"]


# ---------------------------------------------------------------------------
# POST /api/v1/checkin/{session_id}/answer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_answer_returns_next_question(
    client_for_checkin: AsyncClient,
) -> None:
    start = await client_for_checkin.post("/api/v1/checkin/start")
    session_id = start.json()["session_id"]

    resp = await client_for_checkin.post(
        f"/api/v1/checkin/{session_id}/answer",
        json={"answer_text": "María García"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_complete"] is False
    assert data["next_question_text"] is not None
    assert "María García" in data["next_question_text"]
    assert data["employee_name"] is None


@pytest.mark.asyncio
async def test_full_flow_integration(
    client_for_checkin: AsyncClient,
) -> None:
    start = await client_for_checkin.post("/api/v1/checkin/start")
    session_id = start.json()["session_id"]

    answers = [
        "Pedro López",
        "Trabajé en el módulo de pagos",
        "Sin bloqueos hoy",
        "Continuar con las pruebas",
    ]
    last_resp = None
    for answer in answers:
        last_resp = await client_for_checkin.post(
            f"/api/v1/checkin/{session_id}/answer",
            json={"answer_text": answer},
        )
        assert last_resp.status_code == 200

    data = last_resp.json()
    assert data["is_complete"] is True
    assert data["next_question_text"] is None
    assert data["employee_name"] == "Pedro López"


@pytest.mark.asyncio
async def test_answer_unknown_session_returns_404(
    client_for_checkin: AsyncClient,
) -> None:
    resp = await client_for_checkin.post(
        "/api/v1/checkin/does-not-exist/answer",
        json={"answer_text": "Hola"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_answer_completed_session_returns_409(
    client_for_checkin: AsyncClient,
) -> None:
    start = await client_for_checkin.post("/api/v1/checkin/start")
    session_id = start.json()["session_id"]

    answers = ["Ana Ruiz", "Revisé PRs", "Todo bien", "Code review"]
    for answer in answers:
        await client_for_checkin.post(
            f"/api/v1/checkin/{session_id}/answer",
            json={"answer_text": answer},
        )

    # Fifth answer should conflict.
    resp = await client_for_checkin.post(
        f"/api/v1/checkin/{session_id}/answer",
        json={"answer_text": "extra"},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# GET /api/v1/checkin/{session_id}/status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_in_progress(
    client_for_checkin: AsyncClient,
) -> None:
    start = await client_for_checkin.post("/api/v1/checkin/start")
    session_id = start.json()["session_id"]

    resp = await client_for_checkin.get(f"/api/v1/checkin/{session_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "in_progress"
    assert data["questions_answered"] == 0


@pytest.mark.asyncio
async def test_status_returns_questions_answered(
    client_for_checkin: AsyncClient,
) -> None:
    start = await client_for_checkin.post("/api/v1/checkin/start")
    session_id = start.json()["session_id"]

    answers = ["Laura", "Hice deploy", "Un bloqueo en CI", "Revisar logs"]
    for answer in answers:
        await client_for_checkin.post(
            f"/api/v1/checkin/{session_id}/answer",
            json={"answer_text": answer},
        )

    resp = await client_for_checkin.get(f"/api/v1/checkin/{session_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["questions_answered"] == 4
    assert data["employee_name"] == "Laura"


@pytest.mark.asyncio
async def test_status_unknown_session_returns_404(
    client_for_checkin: AsyncClient,
) -> None:
    resp = await client_for_checkin.get("/api/v1/checkin/does-not-exist/status")
    assert resp.status_code == 404
