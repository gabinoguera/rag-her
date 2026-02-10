import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document


@pytest.mark.asyncio
async def test_cosine_similarity_ordering(db_session: AsyncSession) -> None:
    doc = Document(project_title="Vector Search Test")
    db_session.add(doc)
    await db_session.flush()

    # Create 3 vectors with distinct directional differences
    # base_vector: strong signal in first dimensions
    base_vector = [1.0] + [0.0] * 1535

    # similar_vector: close to base (small angle)
    similar_vector = [0.9] + [0.1] + [0.0] * 1534

    # different_vector: orthogonal direction
    different_vector = [0.0] + [1.0] + [0.0] * 1534

    # opposite_vector: opposite direction
    opposite_vector = [-1.0] + [0.0] * 1535

    for i, (emb, label) in enumerate([
        (similar_vector, "similar"),
        (different_vector, "different"),
        (opposite_vector, "opposite"),
    ]):
        chunk = Chunk(
            document_id=doc.id,
            chunk_type="project_overview",
            content_text=label,
            embedding=emb,
        )
        db_session.add(chunk)
    await db_session.flush()

    # Query using cosine distance operator <=>
    stmt = (
        select(Chunk.content_text)
        .where(Chunk.document_id == doc.id)
        .where(Chunk.embedding.isnot(None))
        .order_by(Chunk.embedding.cosine_distance(base_vector))
    )
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    assert rows[0] == "similar"
    assert rows[1] == "different"
    assert rows[2] == "opposite"


@pytest.mark.asyncio
async def test_vector_wrong_dimensions(db_session: AsyncSession) -> None:
    doc = Document(project_title="Wrong Dims Test")
    db_session.add(doc)
    await db_session.flush()

    wrong_dims_vector = [0.1] * 100  # 100 dims instead of 1536
    chunk = Chunk(
        document_id=doc.id,
        chunk_type="project_overview",
        content_text="Wrong dimensions",
        embedding=wrong_dims_vector,
    )
    db_session.add(chunk)
    with pytest.raises(Exception):
        await db_session.flush()
