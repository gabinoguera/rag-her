"""Tests for HER models: Employee, CheckIn, CheckInChunk.

TDD: these tests are written first (RED), then models + migrations are
implemented until all pass (GREEN).
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Employee tests
# ---------------------------------------------------------------------------


async def test_employee_creation(db_session: AsyncSession) -> None:
    """Employee can be created with a name; id and created_at are auto-set."""
    from app.models.employee import Employee

    employee = Employee(name="Ana García")
    db_session.add(employee)
    await db_session.flush()

    assert employee.id is not None
    assert isinstance(employee.id, uuid.UUID)
    assert employee.name == "Ana García"
    assert employee.created_at is not None
    assert isinstance(employee.created_at, datetime)


# ---------------------------------------------------------------------------
# CheckIn tests
# ---------------------------------------------------------------------------


async def test_checkin_creation_with_employee(db_session: AsyncSession) -> None:
    """CheckIn can be created linked to an Employee; defaults are correct."""
    from app.models.checkin import CheckIn
    from app.models.employee import Employee

    employee = Employee(name="Carlos López")
    db_session.add(employee)
    await db_session.flush()

    checkin = CheckIn(
        employee_id=employee.id,
        session_id="sess-abc-001",
    )
    db_session.add(checkin)
    await db_session.flush()

    assert checkin.id is not None
    assert checkin.employee_id == employee.id
    assert checkin.session_id == "sess-abc-001"
    assert checkin.status == "in_progress"
    assert checkin.started_at is not None
    assert checkin.completed_at is None


async def test_checkin_session_id_unique(db_session: AsyncSession) -> None:
    """Two CheckIns cannot share the same session_id."""
    from app.models.checkin import CheckIn
    from app.models.employee import Employee

    employee = Employee(name="María Martínez")
    db_session.add(employee)
    await db_session.flush()

    checkin1 = CheckIn(employee_id=employee.id, session_id="sess-dup-001")
    db_session.add(checkin1)
    await db_session.flush()

    checkin2 = CheckIn(employee_id=employee.id, session_id="sess-dup-001")
    db_session.add(checkin2)

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_checkin_status_values(db_session: AsyncSession) -> None:
    """CheckIn status accepts in_progress, completed, and failed."""
    from app.models.checkin import CheckIn
    from app.models.employee import Employee

    employee = Employee(name="Luis Fernández")
    db_session.add(employee)
    await db_session.flush()

    for status in ("in_progress", "completed", "failed"):
        checkin = CheckIn(
            employee_id=employee.id,
            session_id=f"sess-status-{status}",
            status=status,
        )
        db_session.add(checkin)

    await db_session.flush()


# ---------------------------------------------------------------------------
# CheckInChunk tests
# ---------------------------------------------------------------------------


async def test_checkin_chunk_creation(db_session: AsyncSession) -> None:
    """CheckInChunk can be created linked to a CheckIn with question/answer."""
    from app.models.checkin import CheckIn
    from app.models.checkin_chunk import CheckInChunk
    from app.models.employee import Employee

    employee = Employee(name="Sara Jiménez")
    db_session.add(employee)
    await db_session.flush()

    checkin = CheckIn(employee_id=employee.id, session_id="sess-chunk-001")
    db_session.add(checkin)
    await db_session.flush()

    chunk = CheckInChunk(
        checkin_id=checkin.id,
        question_index=0,
        question_text="¿Cómo te llamas?",
        answer_text="Me llamo Sara",
    )
    db_session.add(chunk)
    await db_session.flush()

    assert chunk.id is not None
    assert chunk.checkin_id == checkin.id
    assert chunk.question_index == 0
    assert chunk.question_text == "¿Cómo te llamas?"
    assert chunk.answer_text == "Me llamo Sara"
    assert chunk.created_at is not None


async def test_checkin_chunk_embedding_nullable(db_session: AsyncSession) -> None:
    """CheckInChunk.embedding is nullable (filled only on check-in completion)."""
    from app.models.checkin import CheckIn
    from app.models.checkin_chunk import CheckInChunk
    from app.models.employee import Employee

    employee = Employee(name="Pedro Sánchez")
    db_session.add(employee)
    await db_session.flush()

    checkin = CheckIn(employee_id=employee.id, session_id="sess-embed-null-001")
    db_session.add(checkin)
    await db_session.flush()

    chunk = CheckInChunk(
        checkin_id=checkin.id,
        question_index=1,
        question_text="¿Cómo fue tu semana?",
        answer_text="Muy bien, gracias",
        embedding=None,
    )
    db_session.add(chunk)
    await db_session.flush()

    assert chunk.embedding is None


async def test_checkin_chunk_embedding_stored(db_session: AsyncSession) -> None:
    """CheckInChunk.embedding stores a 768-dimensional vector correctly."""
    from app.models.checkin import CheckIn
    from app.models.checkin_chunk import CheckInChunk
    from app.models.employee import Employee

    employee = Employee(name="Elena Torres")
    db_session.add(employee)
    await db_session.flush()

    checkin = CheckIn(employee_id=employee.id, session_id="sess-embed-set-001")
    db_session.add(checkin)
    await db_session.flush()

    vector = [0.1] * 768
    chunk = CheckInChunk(
        checkin_id=checkin.id,
        question_index=2,
        question_text="¿Qué logros tuviste?",
        answer_text="Terminé el proyecto X",
        embedding=vector,
    )
    db_session.add(chunk)
    await db_session.flush()

    # Reload from DB to verify persistence
    await db_session.refresh(chunk)
    assert chunk.embedding is not None
    assert len(chunk.embedding) == 768


# ---------------------------------------------------------------------------
# Relationship tests
# ---------------------------------------------------------------------------


async def test_employee_checkin_relationship(db_session: AsyncSession) -> None:
    """Employee.checkins relationship returns all associated CheckIns."""
    from sqlalchemy.orm import selectinload

    from app.models.checkin import CheckIn
    from app.models.employee import Employee

    employee = Employee(name="Lucía Romero")
    db_session.add(employee)
    await db_session.flush()

    checkin1 = CheckIn(employee_id=employee.id, session_id="sess-rel-001")
    checkin2 = CheckIn(employee_id=employee.id, session_id="sess-rel-002")
    db_session.add_all([checkin1, checkin2])
    await db_session.flush()

    # Query with eager load
    result = await db_session.execute(
        select(Employee)
        .where(Employee.id == employee.id)
        .options(selectinload(Employee.checkins))
    )
    loaded_employee = result.scalar_one()

    assert len(loaded_employee.checkins) == 2
    session_ids = {c.session_id for c in loaded_employee.checkins}
    assert session_ids == {"sess-rel-001", "sess-rel-002"}


async def test_checkin_chunks_relationship(db_session: AsyncSession) -> None:
    """CheckIn.chunks relationship returns all associated CheckInChunks."""
    from sqlalchemy.orm import selectinload

    from app.models.checkin import CheckIn
    from app.models.checkin_chunk import CheckInChunk
    from app.models.employee import Employee

    employee = Employee(name="Roberto Gil")
    db_session.add(employee)
    await db_session.flush()

    checkin = CheckIn(employee_id=employee.id, session_id="sess-chunks-rel-001")
    db_session.add(checkin)
    await db_session.flush()

    for i in range(3):
        chunk = CheckInChunk(
            checkin_id=checkin.id,
            question_index=i,
            question_text=f"Pregunta {i}",
            answer_text=f"Respuesta {i}",
        )
        db_session.add(chunk)
    await db_session.flush()

    result = await db_session.execute(
        select(CheckIn)
        .where(CheckIn.id == checkin.id)
        .options(selectinload(CheckIn.chunks))
    )
    loaded_checkin = result.scalar_one()

    assert len(loaded_checkin.chunks) == 3
