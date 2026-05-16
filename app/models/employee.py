import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import MetaData, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.checkin import CheckIn


class HerBase(DeclarativeBase):
    metadata = MetaData(schema="her")


class Employee(HerBase):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    checkins: Mapped[list["CheckIn"]] = relationship(
        "CheckIn", back_populates="employee", cascade="all, delete-orphan"
    )
