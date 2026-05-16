"""Vector storage integration test for her.check_in_chunks.

Rewritten from legacy rag.chunks placeholder in EPIC-002.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkin import CheckIn
from app.models.checkin_chunk import CheckInChunk
from app.models.employee import Employee


async def test_checkin_chunk_embedding_storage(db_session: AsyncSession) -> None:
    """Vector(768) is stored in her.check_in_chunks and retrieved with the same dimension."""
    emp = Employee(name="Vector Test User")
    db_session.add(emp)
    await db_session.flush()

    checkin = CheckIn(employee_id=emp.id, session_id=str(uuid.uuid4()))
    db_session.add(checkin)
    await db_session.flush()

    vector = [float(i) / 768 for i in range(768)]
    chunk = CheckInChunk(
        checkin_id=checkin.id,
        question_index=0,
        question_text="¿Qué lograste esta semana?",
        answer_text="Test de almacenamiento de embeddings.",
        embedding=vector,
    )
    db_session.add(chunk)
    await db_session.flush()
    chunk_id = chunk.id

    db_session.expire(chunk)
    result = await db_session.execute(
        select(CheckInChunk).where(CheckInChunk.id == chunk_id)
    )
    fetched = result.scalar_one()
    assert fetched.embedding is not None
    assert len(fetched.embedding) == 768
    assert abs(fetched.embedding[100] - (100.0 / 768)) < 1e-5
