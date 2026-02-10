from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    project_title: Mapped[str] = mapped_column(Text, nullable=False)
    project_subtitle: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_budget: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False, server_default=text("'EUR'"))
    total_duration_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    technologies: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    client_company_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingestion_status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, server_default=text("'pending'")
    )
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunks_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    chunks: Mapped[list["Chunk"]] = relationship(  # noqa: F821
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    ingestion_logs: Mapped[list["IngestionLog"]] = relationship(  # noqa: F821
        back_populates="document",
    )

    __table_args__ = (
        CheckConstraint(
            "ingestion_status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_documents_ingestion_status",
        ),
        Index("idx_documents_status", "ingestion_status"),
        Index("idx_documents_technologies", "technologies", postgresql_using="gin"),
    )
