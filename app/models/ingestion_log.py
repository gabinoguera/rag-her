import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class IngestionLog(TimestampMixin, Base):
    __tablename__ = "ingestion_logs"

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rag.documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    document: Mapped["Document | None"] = relationship(  # noqa: F821
        back_populates="ingestion_logs",
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('ingest_start', 'validation', 'chunking', 'embedding', "
            "'storage', 'ingest_complete', 'ingest_error', 'delete')",
            name="ck_ingestion_logs_action",
        ),
        CheckConstraint(
            "status IN ('success', 'failure', 'warning')",
            name="ck_ingestion_logs_status",
        ),
        Index("idx_ingestion_logs_document_id", "document_id"),
        Index("idx_ingestion_logs_action_status", "action", "status"),
    )
