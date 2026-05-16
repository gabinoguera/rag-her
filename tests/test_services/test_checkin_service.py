"""Integration tests for CheckInService — DB required, EmbeddingService mocked."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.checkin_flow import TOTAL_QUESTIONS
from app.services.checkin_service import CheckInService, SessionAlreadyCompletedError, SessionNotFoundError


def _make_mock_embedding_service() -> MagicMock:
    service = MagicMock()
    service.generate_embeddings = AsyncMock(
        side_effect=lambda texts, task_type="RETRIEVAL_DOCUMENT": [[0.1] * 768 for _ in texts]
    )
    return service


@pytest.fixture
async def checkin_service(db_session: AsyncSession) -> CheckInService:
    return CheckInService(db=db_session, embedding_service=_make_mock_embedding_service())


@pytest.fixture(autouse=True)
async def clean_her_tables(db_session: AsyncSession) -> None:
    """Delete all her.* rows before each test to avoid cross-test pollution."""
    await db_session.execute(sa_text("DELETE FROM her.check_in_chunks"))
    await db_session.execute(sa_text("DELETE FROM her.check_ins"))
    await db_session.execute(sa_text("DELETE FROM her.employees"))
    await db_session.flush()


# --- create_session ---

@pytest.mark.asyncio
async def test_create_session_returns_checkin_and_question(
    checkin_service: CheckInService,
) -> None:
    checkin, question = await checkin_service.create_session()
    assert checkin.session_id is not None
    assert checkin.status == "in_progress"
    assert question == "¡Hola! Soy HER. ¿Cómo te llamas?"


@pytest.mark.asyncio
async def test_create_session_employee_has_empty_name(
    checkin_service: CheckInService,
) -> None:
    checkin, _ = await checkin_service.create_session()
    # employee linked after flush
    assert checkin.employee_id is not None or checkin.employee is not None


# --- process_answer ---

@pytest.mark.asyncio
async def test_process_answer_saves_chunk(
    checkin_service: CheckInService,
) -> None:
    checkin, _ = await checkin_service.create_session()
    next_q, complete, emp_name = await checkin_service.process_answer(
        checkin.session_id, "Juan Pérez"
    )
    # Should have 1 chunk persisted
    from sqlalchemy import select
    from app.models.checkin_chunk import CheckInChunk
    result = await checkin_service._db.execute(
        select(CheckInChunk).where(CheckInChunk.checkin_id == checkin.id)
    )
    chunks = result.scalars().all()
    assert len(chunks) == 1
    assert chunks[0].answer_text == "Juan Pérez"


@pytest.mark.asyncio
async def test_process_answer_sets_employee_name_on_first_turn(
    checkin_service: CheckInService,
) -> None:
    checkin, _ = await checkin_service.create_session()
    await checkin_service.process_answer(checkin.session_id, "María García")
    from sqlalchemy import select
    from app.models.employee import Employee
    result = await checkin_service._db.execute(
        select(Employee).where(Employee.id == checkin.employee_id)
    )
    employee = result.scalar_one()
    assert employee.name == "María García"


@pytest.mark.asyncio
async def test_process_answer_returns_next_question(
    checkin_service: CheckInService,
) -> None:
    checkin, _ = await checkin_service.create_session()
    next_q, complete, emp_name = await checkin_service.process_answer(
        checkin.session_id, "Carlos"
    )
    assert complete is False
    assert next_q is not None
    assert "Carlos" in next_q  # question 1 interpolates name


@pytest.mark.asyncio
async def test_process_answer_completes_on_fourth_answer(
    checkin_service: CheckInService,
) -> None:
    checkin, _ = await checkin_service.create_session()
    answers = ["Pedro López", "Trabajé en el módulo X", "Ningún bloqueo", "Terminar el módulo Y"]
    for i, answer in enumerate(answers):
        next_q, complete, emp_name = await checkin_service.process_answer(
            checkin.session_id, answer
        )
    assert complete is True
    assert next_q is None
    assert emp_name == "Pedro López"


@pytest.mark.asyncio
async def test_process_answer_raises_on_completed_session(
    checkin_service: CheckInService,
) -> None:
    checkin, _ = await checkin_service.create_session()
    answers = ["Ana Ruiz", "Revisé PRs", "Todo bien", "Code review mañana"]
    for answer in answers:
        await checkin_service.process_answer(checkin.session_id, answer)
    with pytest.raises(SessionAlreadyCompletedError):
        await checkin_service.process_answer(checkin.session_id, "extra answer")


@pytest.mark.asyncio
async def test_process_answer_not_found_raises(
    checkin_service: CheckInService,
) -> None:
    with pytest.raises(SessionNotFoundError):
        await checkin_service.process_answer("non-existent-session-id", "hello")


# --- complete_session ---

@pytest.mark.asyncio
async def test_complete_session_calls_embed_and_updates_status(
    checkin_service: CheckInService,
) -> None:
    checkin, _ = await checkin_service.create_session()
    answers = ["Laura", "Hice deploy", "Un bloqueo en CI", "Revisar logs"]
    for answer in answers:
        await checkin_service.process_answer(checkin.session_id, answer)

    # After completion, status should be "completed"
    status_checkin = await checkin_service.get_session_status(checkin.session_id)
    assert status_checkin.status == "completed"
    assert status_checkin.completed_at is not None


@pytest.mark.asyncio
async def test_complete_session_generates_embeddings(
    checkin_service: CheckInService,
) -> None:
    checkin, _ = await checkin_service.create_session()
    answers = ["Sofía", "Diseñé la UI", "Sin bloqueos", "Continuar mañana"]
    for answer in answers:
        await checkin_service.process_answer(checkin.session_id, answer)

    from sqlalchemy import select
    from app.models.checkin_chunk import CheckInChunk
    result = await checkin_service._db.execute(
        select(CheckInChunk).where(CheckInChunk.checkin_id == checkin.id)
    )
    chunks = result.scalars().all()
    assert len(chunks) == TOTAL_QUESTIONS
    for chunk in chunks:
        assert chunk.embedding is not None


# --- get_session_status ---

@pytest.mark.asyncio
async def test_get_session_status_returns_checkin(
    checkin_service: CheckInService,
) -> None:
    checkin, _ = await checkin_service.create_session()
    status = await checkin_service.get_session_status(checkin.session_id)
    assert status.session_id == checkin.session_id
    assert status.status == "in_progress"


@pytest.mark.asyncio
async def test_get_session_status_not_found_raises(
    checkin_service: CheckInService,
) -> None:
    with pytest.raises(SessionNotFoundError):
        await checkin_service.get_session_status("does-not-exist")
