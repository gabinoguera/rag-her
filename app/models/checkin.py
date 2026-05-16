import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.employee import HerBase

if TYPE_CHECKING:
    from app.models.checkin_chunk import CheckInChunk
    from app.models.employee import Employee


class CheckIn(HerBase):
    __tablename__ = "check_ins"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("her.employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    # Relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="checkins")
    chunks: Mapped[list["CheckInChunk"]] = relationship(
        "CheckInChunk", back_populates="checkin", cascade="all, delete-orphan"
    )
