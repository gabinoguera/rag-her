import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Chunk(TimestampMixin, Base):
    __tablename__ = "chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rag.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_type: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, server_default=text("'{}'::jsonb")
    )
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    total_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(VARCHAR(3), nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="chunks")  # noqa: F821

    __table_args__ = (
        CheckConstraint(
            "chunk_type IN ("
            "'project_overview', 'scope_block', 'line_item', 'phase', 'team_conditions'"
            ")",
            name="ck_chunks_chunk_type",
        ),
        Index("idx_chunks_chunk_type", "chunk_type"),
        Index("idx_chunks_document_id", "document_id"),
        Index("idx_chunks_technologies", "technologies", postgresql_using="gin"),
    )
