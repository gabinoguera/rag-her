from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Float, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SearchLog(TimestampMixin, Base):
    __tablename__ = "search_logs"

    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    chunk_types_filter: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    technologies_filter: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    results_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    top_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    feedback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "feedback_score BETWEEN 1 AND 5",
            name="ck_search_logs_feedback_score",
        ),
    )
