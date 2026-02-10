import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document


@pytest.mark.asyncio
async def test_create_document(db_session: AsyncSession) -> None:
    doc = Document(
        project_title="Test Project",
        raw_json={"key": "value", "nested": {"a": 1}},
    )
    db_session.add(doc)
    await db_session.flush()

    result = await db_session.execute(select(Document).where(Document.id == doc.id))
    fetched = result.scalar_one()
    assert fetched.project_title == "Test Project"
    assert fetched.raw_json == {"key": "value", "nested": {"a": 1}}
    assert fetched.id is not None
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_document_default_values(db_session: AsyncSession) -> None:
    doc = Document(project_title="Defaults Test")
    db_session.add(doc)
    await db_session.flush()

    result = await db_session.execute(select(Document).where(Document.id == doc.id))
    fetched = result.scalar_one()
    assert fetched.ingestion_status == "pending"
    assert fetched.chunks_count == 0
    assert fetched.currency == "EUR"


@pytest.mark.asyncio
async def test_document_technologies_array(db_session: AsyncSession) -> None:
    techs = ["Python", "FastAPI", "PostgreSQL"]
    doc = Document(project_title="Tech Project", technologies=techs)
    db_session.add(doc)
    await db_session.flush()

    result = await db_session.execute(select(Document).where(Document.id == doc.id))
    fetched = result.scalar_one()
    assert fetched.technologies == techs


@pytest.mark.asyncio
async def test_document_status_check_constraint(db_session: AsyncSession) -> None:
    doc = Document(project_title="Bad Status", ingestion_status="invalid_status")
    db_session.add(doc)
    with pytest.raises(IntegrityError):
        await db_session.flush()
