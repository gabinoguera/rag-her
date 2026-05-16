"""Create her.check_ins table.

Revision ID: 008
Revises: 007
Create Date: 2025-01-01 00:00:07.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "check_ins",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column(
            "started_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('in_progress','completed','failed')",
            name="ck_checkins_status",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["her.employees.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_check_ins_session_id"),
        schema="her",
    )

    op.create_index(
        "idx_check_ins_session_id",
        "check_ins",
        ["session_id"],
        schema="her",
    )
    op.create_index(
        "idx_check_ins_employee_id",
        "check_ins",
        ["employee_id"],
        schema="her",
    )


def downgrade() -> None:
    op.drop_index("idx_check_ins_employee_id", table_name="check_ins", schema="her")
    op.drop_index("idx_check_ins_session_id", table_name="check_ins", schema="her")
    op.drop_table("check_ins", schema="her")
