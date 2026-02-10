import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document


@pytest.mark.asyncio
async def test_create_chunk_with_embedding(db_session: AsyncSession) -> None:
    doc = Document(project_title="Embedding Test")
    db_session.add(doc)
    await db_session.flush()

    embedding = [0.1] * 1536
    chunk = Chunk(
        document_id=doc.id,
        chunk_type="project_overview",
        content_text="This is a test chunk",
        embedding=embedding,
    )
    db_session.add(chunk)
    await db_session.flush()

    result = await db_session.execute(select(Chunk).where(Chunk.id == chunk.id))
    fetched = result.scalar_one()
    assert fetched.content_text == "This is a test chunk"
    assert fetched.embedding is not None
    assert len(fetched.embedding) == 1536


@pytest.mark.asyncio
async def test_chunk_document_fk(db_session: AsyncSession) -> None:
    doc = Document(project_title="FK Test")
    db_session.add(doc)
    await db_session.flush()

    chunk = Chunk(
        document_id=doc.id,
        chunk_type="scope_block",
        content_text="Linked to document",
    )
    db_session.add(chunk)
    await db_session.flush()

    result = await db_session.execute(select(Chunk).where(Chunk.document_id == doc.id))
    fetched = result.scalar_one()
    assert fetched.document_id == doc.id


@pytest.mark.asyncio
async def test_chunk_cascade_delete(db_session: AsyncSession) -> None:
    doc = Document(project_title="Cascade Test")
    db_session.add(doc)
    await db_session.flush()

    chunk = Chunk(
        document_id=doc.id,
        chunk_type="line_item",
        content_text="Will be cascade deleted",
    )
    db_session.add(chunk)
    await db_session.flush()

    doc_id = doc.id
    await db_session.delete(doc)
    await db_session.flush()

    result = await db_session.execute(select(Chunk).where(Chunk.document_id == doc_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_chunk_type_check_constraint(db_session: AsyncSession) -> None:
    doc = Document(project_title="Constraint Test")
    db_session.add(doc)
    await db_session.flush()

    chunk = Chunk(
        document_id=doc.id,
        chunk_type="invalid_type",
        content_text="Should fail",
    )
    db_session.add(chunk)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_chunk_metadata_jsonb(db_session: AsyncSession) -> None:
    doc = Document(project_title="Metadata Test")
    db_session.add(doc)
    await db_session.flush()

    metadata = {"section": "backend", "priority": 1, "tags": ["api", "auth"]}
    chunk = Chunk(
        document_id=doc.id,
        chunk_type="phase",
        content_text="Metadata chunk",
        metadata_=metadata,
    )
    db_session.add(chunk)
    await db_session.flush()

    result = await db_session.execute(select(Chunk).where(Chunk.id == chunk.id))
    fetched = result.scalar_one()
    assert fetched.metadata_ == metadata
    assert fetched.metadata_["tags"] == ["api", "auth"]
